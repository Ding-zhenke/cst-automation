"""SDK-free staging and static validation for CST Python result templates."""
import ast
import hashlib
import json
import re
import tempfile
from pathlib import Path


class ResultTemplateError(ValueError):
    """Invalid CST Python result-template input."""


_NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9 _.-]{0,63}$")
_WINDOWS_RESERVED = re.compile(r"^(CON|PRN|AUX|NUL|COM[1-9]|LPT[1-9])(?:\..*)?$", re.IGNORECASE)
_FUNCTION_ARGUMENTS = {
    "define": {"def_params", "calling_app", "prj", "settings"},
    "evaluate": {"eval_params", "calling_app", "prj", "settings"},
}


def validate_python_result_template(source):
    """Validate the documented .rtpy entry points without importing or running them."""
    if not isinstance(source, str) or not source.strip():
        raise ResultTemplateError("Template source must be a nonempty UTF-8 Python file")
    try:
        tree = ast.parse(source)
        compile(tree, "<cst-result-template>", "exec")
    except (SyntaxError, ValueError, TypeError) as exc:
        raise ResultTemplateError(f"Template source is not valid Python: {exc}") from exc

    functions = {
        node.name: node for node in tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    }
    for name, allowed in _FUNCTION_ARGUMENTS.items():
        function = functions.get(name)
        if function is None or isinstance(function, ast.AsyncFunctionDef):
            raise ResultTemplateError(f"Template must define a synchronous top-level {name}() function")
        arguments = function.args
        if arguments.posonlyargs or arguments.defaults or any(value is not None for value in arguments.kw_defaults):
            raise ResultTemplateError(f"{name}() cannot use positional-only parameters or default values")
        positional = [*arguments.posonlyargs, *arguments.args]
        names = [item.arg for item in positional]
        names.extend(item.arg for item in arguments.kwonlyargs)
        if arguments.vararg or arguments.kwarg or any(item.arg not in allowed for item in positional + arguments.kwonlyargs):
            raise ResultTemplateError(f"{name}() parameters must use the documented CST names: {', '.join(sorted(allowed))}")
        if len(names) != len(set(names)):
            raise ResultTemplateError(f"{name}() contains duplicate parameter names")

    return {
        "valid": True,
        "functions": ["define", "evaluate"],
        "validation": "static_syntax_and_signature_only",
        "executed": False,
        "solver_verified": False,
    }


def stage_python_result_template(template_source, library_root, *, group, name):
    """Copy a CST .py/.rtpy module into ``Result Templates/<group>/<name>.rtpy``."""
    if (not isinstance(group, str) or not _NAME.fullmatch(group) or group in (".", "..")
            or group.endswith((".", " ")) or _WINDOWS_RESERVED.fullmatch(group)):
        raise ResultTemplateError("Template group must be one safe folder name (1..64 characters)")
    if (not isinstance(name, str) or not _NAME.fullmatch(name) or name in (".", "..")
            or name.endswith((".", " ")) or _WINDOWS_RESERVED.fullmatch(name)):
        raise ResultTemplateError("Template name must be one safe file name (1..64 characters)")

    source = Path(template_source).resolve()
    if source.suffix.lower() not in (".py", ".rtpy") or not source.is_file():
        raise ResultTemplateError("Template source must be an existing .py or .rtpy file")
    try:
        source_bytes = source.read_bytes()
        source_text = source_bytes.decode("utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        raise ResultTemplateError(f"Cannot read template source as UTF-8: {source}") from exc
    validation = validate_python_result_template(source_text)

    root = Path(library_root).resolve()
    destination = (root / "Result Templates" / group / f"{name}.rtpy").resolve()
    if not destination.is_relative_to(root):
        raise ResultTemplateError("Template destination must remain inside the library root")
    destination.parent.mkdir(parents=True, exist_ok=True)
    try:
        with destination.open("xb") as output:
            output.write(source_bytes)
    except FileExistsError as exc:
        raise ResultTemplateError(f"Template already exists; refusing to overwrite: {destination}") from exc
    except OSError as exc:
        try:
            destination.unlink(missing_ok=True)
        except OSError:
            pass
        raise ResultTemplateError(f"Cannot stage CST result template: {destination}") from exc

    return {
        "path": str(destination),
        "library_root": str(root),
        "library_relative_path": str(destination.relative_to(root)),
        "group": group,
        "name": name,
        "source": str(source),
        "sha256": hashlib.sha256(source_bytes).hexdigest(),
        "bytes": len(source_bytes),
        "validation": validation,
        "native_cst_binding_required": True,
        "readback_verified": False,
        "solver_verified": False,
    }


def inspect_embedded_python_result_template_files(project_resources, *, metadata_path):
    """Audit one supplied, unpacked binding without importing or running its code.

    A resource binding is not proof of native task activation, persistence, or
    automatic evaluation. Unknown metadata/settings are retained verbatim.
    """
    try:
        root = Path(project_resources).resolve()
        ds_root = (root / 'Model' / 'DS').resolve()
        meta = Path(metadata_path).resolve()
        if not ds_root.is_relative_to(root) or not meta.is_relative_to(ds_root) or meta.suffix.lower() != '.rtjson':
            raise ResultTemplateError('Metadata must be an existing .rtjson within project Model/DS')
        metadata_bytes = meta.read_bytes()
        metadata = json.loads(metadata_bytes.decode('utf-8'))
        relative = metadata['template']['python_module']['path']
        if not isinstance(relative, str) or not relative.strip() or Path(relative).is_absolute():
            raise ResultTemplateError('Bound module must use a project-relative path')
        module = (meta.parent / relative).resolve()
        if not module.is_relative_to(ds_root) or module.suffix.lower() not in ('.py', '.rtpy'):
            raise ResultTemplateError('Bound module must remain within project Model/DS')
    except ResultTemplateError:
        raise
    except (OSError, ValueError, KeyError, TypeError, RuntimeError) as exc:
        raise ResultTemplateError('Cannot inspect embedded binding: ' + str(exc)) from exc
    report = {'metadata_path': str(meta), 'metadata': metadata,
              'metadata_sha256': hashlib.sha256(metadata_bytes).hexdigest(),
              'module_path': str(module), 'module_sha256': None, 'module_error': None,
              'validation': None, 'native_binding_verified': False,
              'automatic_update_verified': False, 'settings_semantics_verified': False,
              'solver_verified': False}
    try:
        payload = module.read_bytes()
        report['module_sha256'] = hashlib.sha256(payload).hexdigest()
        report['validation'] = validate_python_result_template(payload.decode('utf-8'))
    except (OSError, UnicodeError, ResultTemplateError) as exc:
        report['module_error'] = f'{type(exc).__name__}: {exc}'
    return report


def replace_embedded_python_result_template(template_source, project_resources, *,
                                            metadata_path, expected_sha256):
    """Replace one already-bound module in opened/unpacked project resources.

    Call after native open, then explicitly save through CST, close/reopen and
    verify. This does not bind a new template, modify settings or persist the
    archive by itself. The existing module hash is required to detect conflicts.
    """
    root = Path(project_resources).resolve()
    ds_root = (root / 'Model' / 'DS').resolve()
    meta = Path(metadata_path).resolve()
    if not isinstance(expected_sha256, str) or not re.fullmatch(r'[0-9a-fA-F]{64}', expected_sha256):
        raise ResultTemplateError('Expected SHA-256 of the existing bound module is required')
    if not ds_root.is_relative_to(root) or not meta.is_relative_to(ds_root) or meta.suffix.lower() != '.rtjson':
        raise ResultTemplateError('Metadata must be an existing .rtjson within project Model/DS')
    try:
        data = json.loads(meta.read_text(encoding='utf-8'))
        relative = data['template']['python_module']['path']
        if not isinstance(relative, str) or not relative.strip() or Path(relative).is_absolute():
            raise ResultTemplateError('Bound module must use a project-relative path')
        module = (meta.parent / relative).resolve()
        if not module.is_relative_to(ds_root) or module.suffix.lower() not in ('.py', '.rtpy') or not module.is_file():
            raise ResultTemplateError('Bound module must already exist within project Model/DS')
        source = Path(template_source).resolve()
        if source.suffix.lower() not in ('.py', '.rtpy'):
            raise ResultTemplateError('Template source must be a .py or .rtpy file')
        payload = source.read_bytes()
        validation = validate_python_result_template(payload.decode('utf-8'))
        before = hashlib.sha256(module.read_bytes()).hexdigest()
        if before != expected_sha256.lower():
            raise ResultTemplateError('Bound module changed; no template replaced')
        temporary = None
        try:
            with tempfile.NamedTemporaryFile(dir=module.parent, prefix=module.name + '.', suffix='.tmp', delete=False) as output:
                temporary = Path(output.name)
                output.write(payload)
            if hashlib.sha256(module.read_bytes()).hexdigest() != before:
                raise ResultTemplateError('Bound module changed during update; no template replaced')
            temporary.replace(module)
        finally:
            if temporary is not None:
                temporary.unlink(missing_ok=True)
    except ResultTemplateError:
        raise
    except (OSError, ValueError, KeyError, TypeError) as exc:
        raise ResultTemplateError('Cannot replace embedded template: ' + str(exc)) from exc
    return {'path': str(module), 'metadata_path': str(meta), 'before_sha256': before,
            'sha256': hashlib.sha256(payload).hexdigest(), 'validation': validation,
            'native_save_required': True, 'readback_verified': False, 'solver_verified': False}


def inspect_embedded_python_result_template(project_resources, *, metadata_path,
                                           expected_settings, expected_sha256=None):
    """Audit an explicit resource triple without claiming native registration.

    Summary.rpp is deliberately not synthesized: its serialization is not a
    documented registration API. A matching entry is necessary evidence only.
    Supply actual resource paths read from the project, never a guessed suffix.
    """
    if not isinstance(expected_settings, dict):
        raise ResultTemplateError('Explicit expected_settings mapping required')
    if expected_sha256 is not None and (not isinstance(expected_sha256, str) or
            not re.fullmatch(r'[0-9a-fA-F]{64}', expected_sha256)):
        raise ResultTemplateError('expected_sha256 must be a SHA-256 hex digest')
    root = Path(project_resources).resolve()
    ds_root = (root / 'Model' / 'DS').resolve()
    meta = Path(metadata_path).resolve()
    if not ds_root.is_relative_to(root) or not meta.is_relative_to(ds_root) or meta.suffix.lower() != '.rtjson':
        raise ResultTemplateError('Metadata must be an existing .rtjson within project Model/DS')
    try:
        data = json.loads(meta.read_text(encoding='utf-8'))
        binding = data['template']
        module_info = binding['python_module']
        if not isinstance(binding, dict) or not isinstance(module_info, dict):
            raise ResultTemplateError('Template and python_module must be mappings')
        relative = module_info['path']
        # Native local copies use a leaf in the same task resource folder.
        if (module_info.get('type') != 'local_copy' or not isinstance(relative, str)
                or not relative or '/' in relative or '\\' in relative or ':' in relative
                or Path(relative).is_absolute()):
            raise ResultTemplateError('Expected an embedded local_copy module in the metadata folder')
        module = (meta.parent / relative).resolve()
        summary = (meta.parent / 'Summary.rpp').resolve()
        if (not module.is_relative_to(meta.parent) or not summary.is_relative_to(meta.parent)
                or module.suffix.lower() not in ('.py', '.rtpy')):
            raise ResultTemplateError('Embedded resource paths escape the task folder')
        if binding['settings'] != expected_settings:
            raise ResultTemplateError('Embedded template settings do not match expected_settings')
        payload = module.read_bytes()
        validation = validate_python_result_template(payload.decode('utf-8'))
        digest = hashlib.sha256(payload).hexdigest()
        if expected_sha256 is not None and digest != expected_sha256.lower():
            raise ResultTemplateError('Embedded source SHA-256 mismatch')
        summary_bytes = summary.read_bytes()
        # This checks the observed exact-name entry, not the undocumented schema.
        if summary_bytes.splitlines().count(meta.stem.encode('utf-8')) != 1:
            raise ResultTemplateError('Summary.rpp must contain exactly one matching result-name entry')
    except ResultTemplateError:
        raise
    except (OSError, UnicodeError, ValueError, KeyError, TypeError) as exc:
        raise ResultTemplateError('Cannot audit embedded template: ' + str(exc)) from exc
    return {'metadata_path': str(meta), 'path': str(module), 'summary_path': str(summary),
            'settings': binding['settings'], 'sha256': digest,
            'summary_sha256': hashlib.sha256(summary_bytes).hexdigest(),
            'validation': validation, 'resource_integrity_verified': True,
            'summary_name_entry_present': True, 'binding_verified': False,
            'readback_verified': False, 'reopen_verified': False, 'solver_verified': False}
