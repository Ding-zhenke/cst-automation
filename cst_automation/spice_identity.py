"""Conservative file/pin identity evidence. No CST imports or model evaluation."""
import hashlib
from pathlib import Path
import re
from datetime import datetime, timezone


def _snapshot(path):
    result = {'path': str(path), 'read_at': datetime.now(timezone.utc).isoformat(),
              'sha256': None, 'size_bytes': None, 'error': None}
    try:
        data = path.read_bytes()
        result.update(sha256=hashlib.sha256(data).hexdigest(), size_bytes=len(data))
        return result, data
    except OSError as exc:
        result['error'] = f'{type(exc).__name__}: {exc}'
        return result, None


def source_contract(path, model):
    """Snapshot and parse only simple, unique SUBCKT headers; never expand includes."""
    snapshot, data = _snapshot(Path(path))
    contract = {'snapshot': snapshot, 'pins': None, 'dependency_closure_verified': None,
                'parse_error': None}
    if data is None:
        contract['parse_error'] = snapshot['error']
        return contract
    try:
        lines = data.decode('utf-8-sig').splitlines()
    except UnicodeError as exc:
        contract['parse_error'] = f'{type(exc).__name__}: {exc}'
        return contract
    meaningful = [line.strip() for line in lines if line.strip() and not line.lstrip().startswith('*')]
    dependencies = any(re.match(r'\.(?:include|inc|lib)\b', line, re.I) for line in meaningful)
    contract['dependency_closure_verified'] = None if dependencies else True
    headers = []
    for index, line in enumerate(meaningful):
        tokens = line.split()
        if len(tokens) >= 2 and tokens[0].casefold() == '.subckt' and tokens[1] == model:
            pins = tokens[2:]
            continued = index + 1 < len(meaningful) and meaningful[index + 1].startswith('+')
            if (not pins or len(set(pins)) != len(pins) or continued or
                    any(not re.fullmatch(r'[A-Za-z0-9_]+', pin) for pin in pins)):
                contract['parse_error'] = 'Unsupported SUBCKT port declaration'
            headers.append(pins)
    if len(headers) == 1 and contract['parse_error'] is None:
        contract['pins'] = headers[0]
    else:
        contract['parse_error'] = contract['parse_error'] or 'Selected SUBCKT is missing or not unique'
    return contract


def verify_spice_identity(settings, native_reference, project_path, block_name, actual, pins):
    """Tri-state dimensions; unknown never becomes verified through path equality."""
    source = settings['source_contract']
    report = {'requested_source_path': settings['file'], 'native_file_reference': native_reference,
              'project_path': project_path, 'block_name': block_name,
              'resolution_base': None, 'resolved_cache_path': None,
              'source_snapshot': source['snapshot'], 'cache_snapshot': None,
              'expected_pins': source['pins'], 'actual_pins': pins,
              'source_parse_error': source['parse_error'], 'resolution_error': None,
              'source_content_verified': None, 'cache_ownership_verified': None,
              'pin_mapping_verified': None, 'model_verified': actual.get('spice_model') == settings['spice_model'],
              'dialect_verified': None, 'dependency_closure_verified': source['dependency_closure_verified'],
              'reference_kind': 'unknown', 'saved_reopen_verified': False,
              'connection_mapping_verified': None, 'solver_verified': False}
    if settings['spice_filter'] is not None:
        report['dialect_verified'] = str(actual.get('spice_filter', '')).casefold() == settings['spice_filter'].casefold()
    if source['pins'] is not None:
        names = [pin.get('pin_name') for pin in pins]
        report['pin_mapping_verified'] = names == source['pins']
    try:
        project = Path(project_path) if project_path else None
        if project is not None and not project.is_absolute():
            raise ValueError('Absolute bound project path required')
        if project is not None:
            project = project.resolve()
            report['resolution_base'] = str(project.parent)
        if not isinstance(native_reference, str) or not native_reference.strip():
            raise ValueError('Native file reference missing')
        cache = Path(native_reference)
        if not cache.is_absolute():
            if project is None:
                raise ValueError('Relative cache reference requires bound project path')
            cache = project.parent / cache
        cache = cache.resolve()
        report['resolved_cache_path'] = str(cache)
        if cache == Path(settings['file']):
            report['reference_kind'] = 'source_reference'
        elif project is not None:
            # An exact block-specific dependency directory, not a substring test.
            root = project.with_suffix('') / 'Model' / 'DS' / 'Block'
            owner = root / block_name
            safe_name = block_name not in ('.', '..') and not any(c in block_name for c in '/\\:')
            resources = project.with_suffix('')
            if safe_name and owner in cache.parents:
                report['cache_ownership_verified'] = True
            elif resources not in cache.parents:
                report['cache_ownership_verified'] = False
            # Other layouts within these project resources have no calibrated
            # block binding (numeric IDs may be legitimate). Keep them unknown.
            report['reference_kind'] = 'project_cache'
        snapshot, _ = _snapshot(cache)
        report['cache_snapshot'] = snapshot
        if snapshot['sha256'] is not None:
            report['source_content_verified'] = snapshot['sha256'] == source['snapshot']['sha256']
    except (OSError, ValueError) as exc:
        report['resolution_error'] = f'{type(exc).__name__}: {exc}'
    dimensions = ['source_content_verified', 'cache_ownership_verified', 'pin_mapping_verified',
                  'model_verified', 'dependency_closure_verified']
    if settings['spice_filter'] is not None:
        dimensions.append('dialect_verified')
    report['verification_complete'] = all(report[key] is True for key in dimensions)
    report['mismatches'] = [key for key in dimensions if report[key] is False]
    return report
