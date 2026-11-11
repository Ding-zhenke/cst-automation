"""Repair ADS Agent Bridge 0.2.0a2 DE context menus on ADS 2025.

Run with the Bridge installation's Python. Does not restart ADS or run a solver.
"""
from __future__ import annotations
import argparse
import hashlib
import importlib.metadata
import importlib.resources
import json
import os
from pathlib import Path
import shutil
import tempfile

OLD = '''        self._de_app.add_main_popup_callback(
            self._guard(self._de_main_popup), DE_MAIN_POPUP_CALLBACK
        )'''
NEW = '''        add_main_popup = getattr(self._de_app, "add_main_popup_callback", None)
        if callable(add_main_popup):
            add_main_popup(self._guard(self._de_main_popup), DE_MAIN_POPUP_CALLBACK)'''
OLD_TEST = 'if callable(getattr(experimental, "selected_workspace_items", None))'
NEW_TEST = 'if callable(add_main_popup)\n                and callable(getattr(experimental, "selected_workspace_items", None))'

def transform(text: str) -> tuple[str, bool]:
    newline = '\r\n' if '\r\n' in text else '\n'
    text = text.replace('\r\n', '\n')
    if text.count(NEW) == 1 and text.count(NEW_TEST) == 1 and OLD not in text:
        return text.replace('\n', newline), False
    if text.count(OLD) != 1 or text.count(OLD_TEST) != 1:
        raise ValueError('Unrecognized Bridge source; inspect upstream compatibility instead of patching.')
    return text.replace(OLD, NEW).replace(OLD_TEST, NEW_TEST).replace('\n', newline), True

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--apply', action='store_true', help='Apply after reviewing dry-run output')
    parser.add_argument('--addon-file', type=Path, required=True, help='Registered de_entrypoint.py sibling context_ui.py')
    args = parser.parse_args()
    version = importlib.metadata.version('ads-agent-bridge')
    if version != '0.2.0a2':
        raise SystemExit(f'Unsupported Bridge version {version}; do not apply this patch.')
    source = Path(str(importlib.resources.files('ads_agent_bridge.addon').joinpath('AdsAgentBridge', 'context_ui.py'))).resolve()
    targets = list(dict.fromkeys([source, args.addon_file.resolve()]))
    plans = []
    for path in targets:
        raw = path.read_bytes()
        original = raw.decode('utf-8')
        updated, changed = transform(original)
        backup = path.with_name(path.name + '.before_ads2025_compat.bak')
        if changed and backup.exists():
            raise SystemExit(f'Backup already exists: {backup}; inspect before proceeding.')
        plans.append((path, raw, updated.encode('utf-8'), changed, backup))
    for path, raw, updated, changed, backup in plans:
        if args.apply and changed:
            shutil.copy2(path, backup)
            fd, name = tempfile.mkstemp(prefix='.bridge-', dir=path.parent)
            try:
                with os.fdopen(fd, 'wb') as f: f.write(updated)
                os.replace(name, path)
            finally:
                if os.path.exists(name): os.unlink(name)
        print(json.dumps({'path': str(path), 'changed': changed, 'applied': bool(args.apply and changed), 'original_sha256': hashlib.sha256(raw).hexdigest(), 'backup': str(backup) if changed else None}))

if __name__ == '__main__':
    main()
