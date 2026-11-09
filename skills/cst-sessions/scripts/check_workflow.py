"""Read-only checklist consistency check; never connects to or authorizes CST."""
import argparse
import hashlib
import json
from pathlib import Path


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False)


def basis_digest(manifest, name):
    """Bind an observation to identity, expected value and declared dependencies."""
    try:
        identity = manifest['identity']
        if not isinstance(identity, dict) or any(
            not isinstance(identity.get(k), str) or not identity[k].strip()
            for k in ('project_id', 'recovery_reference')
        ):
            raise ValueError('Explicit project_id and recovery_reference required')
        requirement = manifest['requirements'][name]
        keys = requirement['depends_on']
        if not isinstance(keys, list) or not keys or any(not isinstance(k, str) or not k for k in keys):
            raise ValueError('Nonempty depends_on required')
        if len(set(keys)) != len(keys):
            raise ValueError('Duplicate dependency')
        basis = {'identity': identity, 'expected': requirement['expected'],
                 'inputs': {k: manifest['inputs'][k] for k in keys}}
        return hashlib.sha256(canonical(basis).encode('utf-8')).hexdigest()
    except (KeyError, TypeError) as exc:
        raise ValueError(f'Invalid requirement {name}: {exc}') from exc


def json_pointer(document, pointer):
    if not isinstance(pointer, str) or (pointer and not pointer.startswith('/')):
        raise ValueError('Evidence pointer must be an RFC 6901 JSON pointer')
    if pointer == '':
        return document
    for raw in pointer[1:].split('/'):
        # Reject malformed escapes rather than silently selecting another key.
        import re
        if re.search(r'~(?![01])', raw):
            raise ValueError('Invalid JSON pointer escape')
        key = raw.replace('~1', '/').replace('~0', '~')
        if isinstance(document, list):
            if not key.isascii() or not key.isdigit() or (len(key) > 1 and key[0] == '0'):
                raise ValueError('Invalid array index')
            document = document[int(key)]
        elif isinstance(document, dict):
            document = document[key]
        else:
            raise ValueError('Evidence pointer traverses a scalar')
    return document


def check(manifest, stage, base_dir):
    """Check declared requirements, not checklist completeness or physical validity."""
    if type(manifest.get('schema_version')) is not int or manifest['schema_version'] != 1:
        raise ValueError('Expected schema_version 1')
    stages = manifest.get('stages')
    if not isinstance(stages, dict) or stage not in stages:
        raise ValueError('Unknown stage')
    names = stages[stage]
    if not isinstance(names, list) or not names or any(not isinstance(n, str) or not n for n in names):
        raise ValueError('Stage requires a nonempty requirement list')
    if len(set(names)) != len(names):
        raise ValueError('Duplicate stage requirement')
    observations = manifest.get('observations', {})
    if not isinstance(observations, dict):
        raise ValueError('observations must be an object')
    blockers = []
    for name in names:
        basis = basis_digest(manifest, name)
        observation = observations.get(name)
        code = None
        detail = None
        if not isinstance(observation, dict):
            code = 'missing_observation'
        elif observation.get('basis_sha256') != basis:
            code = 'stale_basis'
        else:
            try:
                path = observation['path']
                if not isinstance(path, str) or not path.strip():
                    raise ValueError('Missing evidence path')
                data = (Path(base_dir) / path).read_bytes()
                if hashlib.sha256(data).hexdigest() != observation['sha256']:
                    code = 'artifact_changed'
                else:
                    actual = json_pointer(json.loads(data.decode('utf-8-sig')), observation['pointer'])
                    if canonical(actual) != canonical(manifest['requirements'][name]['expected']):
                        code = 'value_mismatch'
            except (OSError, KeyError, IndexError, TypeError, ValueError) as exc:
                code, detail = 'unreadable_evidence', str(exc)
        if code:
            blockers.append({'requirement': name, 'code': code, 'detail': detail})
    return {'stage': stage, 'consistent': not blockers, 'blockers': blockers,
            'scope': 'declared checklist only; no native verification or execution authorization'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('manifest', type=Path)
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument('--stage')
    action.add_argument('--basis', metavar='REQUIREMENT')
    args = parser.parse_args()
    try:
        manifest = json.loads(args.manifest.read_text(encoding='utf-8-sig'))
        if not isinstance(manifest, dict):
            raise ValueError('Manifest must be an object')
        if args.basis:
            print(basis_digest(manifest, args.basis))
            return 0
        result = check(manifest, args.stage, args.manifest.parent)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0 if result['consistent'] else 1
    except (OSError, ValueError, TypeError) as exc:
        print(json.dumps({'consistent': False, 'error': str(exc)}, ensure_ascii=False))
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
