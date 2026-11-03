"""Inventory installed Python APIs and explicit session routes without CST."""
import argparse
import inspect
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def inventory():
    from cst_solver import setup as CstSetup
    from tpc_service.sessions.model_api import METHODS
    records = []
    for name, method in inspect.getmembers(CstSetup, callable):
        if name.startswith('_'):
            continue
        owner = next((c.__name__ for c in CstSetup.__mro__ if name in c.__dict__), 'unknown')
        source = Path(inspect.getsourcefile(method)).resolve()
        records.append(dict(name=name, owner=owner, signature=str(inspect.signature(method)),
                            source=source.relative_to(ROOT).as_posix(),
                            line=inspect.getsourcelines(method)[1],
                            session_model_api=name in METHODS,
                            native_validation='not established by inventory'))
    return dict(sdk_imported=any(n == 'cst' or n.startswith('cst.') for n in sys.modules),
                public_methods=len(records), session_model_api_methods=len(METHODS),
                methods=records)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    destination = args.output.resolve()
    if ROOT not in destination.parents:
        parser.error('Output must remain in the repository')
    destination.mkdir(parents=True, exist_ok=True)
    report = inventory()
    (destination / 'capabilities.json').write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    lines = ['# Python API / session route inventory', '',
             f'Public methods: {report["public_methods"]}; explicit model_api methods: '
             f'{report["session_model_api_methods"]}; CST SDK imported: {report["sdk_imported"]}.', '',
             'This inventories availability, not native behavior or solver acceptance.', '',
             '| Family | Method | Signature | model_api | Source |',
             '|---|---|---|---|---|']
    for item in report['methods']:
        signature = item['signature'].replace('|', '&#124;')
        lines.append(f'| {item["owner"]} | {item["name"]} | `{signature}` | '
                     f'{item["session_model_api"]} | {item["source"]}:{item["line"]} |')
    (destination / 'capabilities.md').write_text('\n'.join(lines) + '\n', encoding='utf-8')
    print(json.dumps({k: v for k, v in report.items() if k != 'methods'}))


if __name__ == '__main__':
    main()
