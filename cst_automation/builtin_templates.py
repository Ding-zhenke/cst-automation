"""CST 2026.1 built-in VBA template resources (v11 index, v3 settings)."""
import math
import re
import struct
from pathlib import Path, PureWindowsPath

from .result_templates import ResultTemplateError
from .template_registration import RESULT_TYPES


def component(value):
    if (not isinstance(value, str) or not value.strip() or value in ('.', '..')
            or value.endswith(('.', ' ')) or PureWindowsPath(value).is_reserved()
            or re.search(r'[\\/:*?"<>|\x00-\x1f]', value)):
        raise ResultTemplateError('Invalid template name or path component: ' + repr(value))
    return value


def resolve_template(library, category, name, context):
    root = Path(library).resolve()
    folder = (root / component(category)).resolve()
    component(name)
    if folder.parent != root or not folder.is_dir():
        raise ResultTemplateError('Unknown built-in template category: ' + category)
    matches = []
    for file in folder.glob('*.rtp'):
        title, _, suffix = file.stem.partition('^')
        if title.removeprefix('- ').casefold() != name.removeprefix('- ').casefold():
            continue
        flags = re.findall(r'([+-])([A-Za-z0-9]+)', suffix)
        included = {app for sign, app in flags if sign == '+'}
        if (included and context not in included) or ('-', context) in flags:
            continue
        if file.resolve().parent == folder and file.is_file():
            matches.append(file)
    if len(matches) != 1:
        raise ResultTemplateError(f'Expected one installed {context} VBA template for {category}/{name}, found {len(matches)}')
    return matches[0]


def _scalar(value):
    if isinstance(value, bool):
        return '1' if value else '0'
    if isinstance(value, float) and not math.isfinite(value):
        raise ResultTemplateError('Template settings must be finite')
    if not isinstance(value, (str, float, int)) or '\x00' in str(value):
        raise ResultTemplateError('Expected a scalar template setting')
    return str(value)


def touchstone_settings(settings, context):
    defaults = dict(ReferenceImpedance=50, NumberOfSamples=101, FormatG=0,
                    Renormalize=True, UseAR=False, LimitFreqRange=False, FMin='fmin', FMax='fmax')
    allowed = {'TaskName', 'ReferenceImpedance'} if context == 'DS' else defaults.keys()
    if settings.keys() - allowed:
        raise ResultTemplateError(f'Unsupported Touchstone Export settings for {context}: {settings.keys() - allowed}')
    config = {**defaults, **settings}
    if context == 'DS':
        task = config.pop('TaskName', None)
        if not isinstance(task, str) or not task or any(not part or part in ('.', '..')
                or re.search(r'[\x00-\x1f/]', part) for part in task.split('\\')):
            raise ResultTemplateError('DS Touchstone Export requires TaskName (an existing S-Parameters task)')
    value = float(_scalar(config['ReferenceImpedance']))
    if not math.isfinite(value) or value <= 0:
        raise ResultTemplateError('ReferenceImpedance must be positive and finite')
    samples = _scalar(config['NumberOfSamples'])
    if not samples.isascii() or not samples.isdecimal() or not 2 <= int(samples) <= 2147483647:
        raise ResultTemplateError('NumberOfSamples must be an integer from 2 to 2147483647')
    fmt = _scalar(config['FormatG']).upper()
    config['FormatG'] = {'MA': '0', 'RI': '1', 'DB': '2'}.get(fmt, fmt)
    if config['FormatG'] not in ('0', '1', '2'):
        raise ResultTemplateError('FormatG must be MA, RI, DB or 0, 1, 2')
    for key in ('Renormalize', 'UseAR', 'LimitFreqRange'):
        if _scalar(config[key]) not in ('0', '1'):
            raise ResultTemplateError(key + ' must be boolean or 0/1')
    if _scalar(config['LimitFreqRange']) == '1':
        lo, hi = config['FMin'], config['FMax']
        for bound in (lo, hi):
            if not _scalar(bound).strip():
                raise ResultTemplateError('Frequency limits require numbers or project parameter names')
        try:
            bounds = float(lo), float(hi)
        except ValueError:
            pass  # Native project parameter names are also supported by this template.
        else:
            if not all(map(math.isfinite, bounds)) or bounds[0] >= bounds[1]:
                raise ResultTemplateError('Require finite FMin < FMax')
    return config


def prepare(library, category, name, settings, context, result_type, evaluation_type):
    if not isinstance(settings, dict):
        raise ResultTemplateError('settings must be a mapping')
    file = resolve_template(library, category, name, context)
    source = file.read_bytes()
    text = source.decode('latin1')
    # Ignore commented-out VBA statements; do not run Define or its dialog.
    code = '\n'.join(line for line in text.splitlines() if not line.lstrip().startswith(("'", 'Rem ')))
    if category.casefold() == 's-parameters' and file.stem.startswith('- Touchstone Export^'):
        values = touchstone_settings(settings, context)
    else:
        values = settings.copy()
    def declaration(key, supplied, choices, default=None):
        calls = re.findall(r'\bStoreTemplateSetting\s*\(\s*"' + key + r'"\s*,\s*([^\r\n]+)', code, re.I)
        matches = [re.fullmatch(r'"([^"]+)"\s*\)\s*(?:\x27.*)?', call) for call in calls]
        literals = {match[1] for match in matches if match}
        if supplied is not None and supplied not in choices:
            raise ResultTemplateError('Invalid ' + key)
        if not calls and default:
            if supplied not in (None, default):
                raise ResultTemplateError('Incompatible ' + key + ' for a legacy template')
            return default
        if supplied is not None and literals and all(matches) and supplied not in literals:
            raise ResultTemplateError('Incompatible literal ' + key)
        if len(literals) == 1 and all(matches):
            value = literals.pop()
            if supplied not in (None, value) or value not in choices:
                raise ResultTemplateError('Incompatible literal ' + key)
            return value
        if supplied is not None:
            return supplied
        raise ResultTemplateError('Specify ' + key + ' explicitly for a dynamic template')
    kind = declaration('TemplateType', result_type, RESULT_TYPES)
    mode = declaration('EvaluationType', evaluation_type, ('legacy', 'single_run', 'all_runs'), 'legacy')
    keys = set(re.findall(r'\b(?:Get|Store)ScriptSetting\s*\(\s*"([^"]+)"', code, re.I))
    if values.keys() - keys:
        raise ResultTemplateError(f'Unknown scalar template settings: {values.keys() - keys}')
    native = {key: _scalar(value) for key, value in values.items()}
    native['TemplateType'] = kind
    if mode != 'legacy':
        native['EvaluationType'] = mode
    return file, source, native, kind, mode


def append_index(current, result, title, category, filename, kind, mode, tree_refs):
    """Append a row while preserving existing order, output names and tree-reference IDs."""
    lines = current.decode('utf-8-sig').splitlines() if current else ['11', '0', '0', '0']
    def number(index):
        if index >= len(lines) or not re.fullmatch(r'[0-9]+', lines[index]):
            raise ResultTemplateError('Malformed CST template index')
        return int(lines[index])
    if lines[:3] != ['11', '0', '0']:
        raise ResultTemplateError('Unsupported CST template index header')
    count = number(3)
    pos = 4
    names = set()
    for _ in range(count):
        if pos+9 >= len(lines) or lines[pos+8] not in ('Python', 'VBA'):
            raise ResultTemplateError('Unsupported existing template row')
        names.add(lines[pos].casefold())
        pos += 10 + number(pos+9)
    if result.casefold() in names:
        raise ResultTemplateError('A result template with this result name already exists: ' + result)
    ref_count = number(pos) if pos < len(lines) else 0
    refs = lines[pos+1:]
    if pos > len(lines) or len(refs) != ref_count or (pos == len(lines) and count):
        raise ResultTemplateError('Incomplete template reference table')
    mapping = {}
    for row in refs:
        idx, sep, value = row.partition(':')
        if not sep or not re.fullmatch(r'[1-9][0-9]*', idx) or int(idx) in mapping:
            raise ResultTemplateError('Malformed template tree reference')
        mapping[int(idx)] = value
    encoded_refs = {}
    for key, path in tree_refs.items():
        if not isinstance(key, str) or not key or not isinstance(path, str) or not path or re.search(r'[\x00-\x1f]', key+path):
            raise ResultTemplateError('Invalid tree reference')
        idx = next((i for i, v in mapping.items() if v == path), None)
        if idx is None:
            idx = max(mapping, default=0) + 1
            mapping[idx] = path
            refs.append(f'{idx}:{path}')
        encoded_refs['TemplateTreeName/' + key] = str(idx)
    layout = {'legacy': 'ED10', 'single_run': 'EP10', 'all_runs': 'EP11'}[mode]
    new = [*lines[:3], str(count+1), *lines[4:pos], result, title, '1', kind,
           category, 'P', layout, filename, 'VBA', '0', str(len(refs)), *refs]
    return ('\r\n'.join(new)+'\r\n').encode('utf-8'), encoded_refs


def settings_resource(source, values):
    def field(value):
        return struct.pack('<I', len(value)+1) + value + b'\0'
    if b'\0' in source:
        raise ResultTemplateError('Unsupported binary VBA source')
    version = field(b'2026|1|20251022')
    fields = b''.join(field(k.encode()) + field(v.encode()) for k, v in sorted(values.items()))
    return struct.pack('<II', 3, 0) + version*2 + struct.pack('<I', len(values)) + fields + field(source)
