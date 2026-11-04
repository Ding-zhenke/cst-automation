"""Versioned CST Python registration resources; no SDK or template execution.

This deliberately supports one registration in a dedicated Post task. It is
not a general parser for all historical/proprietary Result Template formats.
"""
import ast
import hashlib
import json
from pathlib import Path

from .result_templates import ResultTemplateError, _NAME, _WINDOWS_RESERVED, validate_python_result_template

SUPPORTED_NATIVE_VERSION = 'Version 2026.1 - Oct 22 2025'
STUDIO_VERSION = [2026, 1, 20251022]
RESULT_TYPES = ('0D', '1D', '1DC', 'M0D', 'M1D', 'M1DC')


def safe_name(value):
    if (not isinstance(value, str) or not _NAME.fullmatch(value) or value.endswith(('.', ' '))
            or _WINDOWS_RESERVED.fullmatch(value)):
        raise ResultTemplateError('Expected a safe ASCII registration name (1..64 characters)')
    return value


def prepare_python_result_registration(template_source, *, result_name, template_name,
                                       group, result_type, settings, eval_type='single_run'):
    """Compile a resource payload, without executing even define()."""
    for name in (result_name, template_name, group):
        safe_name(name)
    if result_type not in RESULT_TYPES:
        raise ResultTemplateError('Unsupported result_type')
    if eval_type != 'single_run':
        raise ResultTemplateError('Only the observed single_run registration format is supported')
    if not isinstance(settings, dict):
        raise ResultTemplateError('Explicit settings mapping required')
    def check(value):
        if isinstance(value, dict):
            if not all(isinstance(k, str) for k in value):
                raise ResultTemplateError('Template settings keys must be strings')
            for child in value.values(): check(child)
        elif isinstance(value, list):
            for child in value: check(child)
        elif value is not None and type(value) not in (str, bool, int, float):
            raise ResultTemplateError('Template settings must contain JSON values')
    check(settings)
    try:
        settings = json.loads(json.dumps(settings, allow_nan=False))
        source = Path(template_source).resolve()
        if source.suffix.lower() not in ('.py', '.rtpy'):
            raise ResultTemplateError('An existing .py or .rtpy source is required')
        code = source.read_bytes()
        source_text = code.decode('utf-8')
        validate_python_result_template(source_text)
        # Do not execute define(). Reject an explicitly incompatible literal;
        # dynamic declarations remain the caller's responsibility.
        define = next(n for n in ast.parse(source_text).body if isinstance(n, ast.FunctionDef) and n.name == 'define')
        for node in ast.walk(define):
            if isinstance(node, ast.Call) and (
                    isinstance(node.func, ast.Name) and node.func.id == 'TemplateSettings'
                    or isinstance(node.func, ast.Attribute) and node.func.attr == 'TemplateSettings'):
                for keyword in node.keywords:
                    if (keyword.arg == 'eval_type' and isinstance(keyword.value, ast.Constant)
                            and keyword.value.value != eval_type):
                        raise ResultTemplateError('Source define() eval_type differs from the requested single_run format')
    except (OSError, UnicodeError, ValueError, TypeError) as exc:
        raise ResultTemplateError(str(exc)) from exc
    row = [result_name, template_name, '1', result_type, group, 'P',
           'EP10', template_name + '.rtpy', 'Python', '0', '0']
    metadata = {'version': [1, 0], 'template': {
        'python_module': {'path': result_name + '.rtpy', 'type': 'local_copy'},
        'renamed_by_user': False, 'settings': settings,
        'studio_version_0': STUDIO_VERSION, 'studio_version_c': STUDIO_VERSION}}
    return {'Summary.rpp': ('\r\n'.join(['11', '0', '0', '1', *row]) + '\r\n').encode('utf-8'),
            result_name + '.rtjson': json.dumps(metadata, ensure_ascii=False, allow_nan=False,
                                                indent=4).encode('utf-8'),
            result_name + '.rtpy': code}


def payload_digest(payload):
    manifest = {name: hashlib.sha256(value).hexdigest() for name, value in payload.items()}
    digest = hashlib.sha256(json.dumps(manifest, sort_keys=True).encode('utf-8')).hexdigest()
    return digest, manifest


def inspect_python_result_registration(folder):
    """Read the complete supported registration, not just file presence."""
    folder = Path(folder).resolve()
    try:
        summary = (folder / 'Summary.rpp').read_bytes()
        lines = summary.decode('utf-8-sig').splitlines()
        if len(lines) < 15 or lines[:4] != ['11', '0', '0', '1']:
            raise ResultTemplateError('Expected exactly one CST 2026.1 registration; other formats/counts refused')
        name, title, enabled, kind, group, evaluation, layout, library_file, language = lines[4:13]
        for text in (name, title, group): safe_name(text)
        if (enabled != '1' or kind not in RESULT_TYPES or evaluation != 'P' or layout != 'EP10'
                or language != 'Python' or library_file != title + '.rtpy' or lines[-1] != '0'):
            raise ResultTemplateError('Unsupported registration flags or inconsistent descriptor')
        count_text = lines[13]
        if not count_text.isascii() or not count_text.isdecimal():
            raise ResultTemplateError('Invalid native output count')
        output_count = int(count_text)
        if len(lines) != 15 + output_count or (output_count and kind != 'M0D'):
            raise ResultTemplateError('Unsupported or inconsistent native output descriptor')
        output_names = lines[14:-1]
        prefix = name + '_'
        if (len(set(output_names)) != output_count or any(
                not value.startswith(prefix) or len(value) == len(prefix)
                or any(ord(char) < 32 or char in '/\\' for char in value)
                for value in output_names)):
            raise ResultTemplateError('Native output names are ambiguous or belong to another registration')
        meta = folder / (name + '.rtjson')
        module = folder / (name + '.rtpy')
        for path in (folder / 'Summary.rpp', meta, module):
            if path.resolve().parent != folder:
                raise ResultTemplateError('Registration resource escapes its task folder')
        data = json.loads(meta.read_text(encoding='utf-8'))
        template = data['template']
        if data['version'] != [1, 0] or template['python_module'] != {'path': module.name, 'type': 'local_copy'}:
            raise ResultTemplateError('Unsupported metadata version or nonlocal module')
        settings = template['settings']
        if not isinstance(settings, dict):
            raise ResultTemplateError('Template settings must be a mapping')
        payload = {'Summary.rpp': summary, meta.name: meta.read_bytes(), module.name: module.read_bytes()}
        validate_python_result_template(payload[module.name].decode('utf-8'))
        digest, manifest = payload_digest(payload)
    except ResultTemplateError:
        raise
    except (OSError, UnicodeError, ValueError, TypeError, KeyError) as exc:
        raise ResultTemplateError('Cannot read registration: ' + str(exc)) from exc
    return {'result_name': name, 'template_name': title, 'group': group, 'result_type': kind,
            'native_output_count': output_count, 'native_output_names': output_names,
            'eval_type': None, 'eval_type_status': 'not_independently_decoded',
            'raw_evaluation_flags': {'flag': evaluation, 'layout': layout},
            'settings': settings, 'registration_sha256': digest,
            'manifest': manifest, 'folder': str(folder), 'native_template_enumeration_verified': False,
            'template_execution_verified': False}


def check_registration_conflict(folder, payload, *, conflict='error', expected_registration_sha256=None):
    """Preflight every target before the native chain or resources are changed."""
    folder = Path(folder)
    if conflict not in ('error', 'replace'):
        raise ResultTemplateError('conflict must be error or replace')
    if conflict == 'replace':
        before = inspect_python_result_registration(folder)
        if not isinstance(expected_registration_sha256, str) or before['registration_sha256'] != expected_registration_sha256:
            raise ResultTemplateError('Expected complete registration SHA-256 mismatch')
        if set(before['manifest']) != set(payload):
            raise ResultTemplateError('Replacement must retain the same registration identity')
        return before
    if expected_registration_sha256 is not None:
        raise ResultTemplateError('Expected digest is only valid for conflict=replace')
    if any((folder / name).exists() for name in payload):
        raise ResultTemplateError('Registration already exists; refusing to overwrite')
    return None
