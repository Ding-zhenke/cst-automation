"""Explicit fake CST boundary for offline session demos; never native evidence."""
import json
from pathlib import Path
from types import SimpleNamespace


class OfflineApp:
    def __init__(self):
        self.project = SimpleNamespace(close=lambda: None)
        self.cst_file = None

    def new_project(self):
        self.cst_file = {'parameters': {}, 'history': [], 'type': 'MWS'}

    def new_circuit_project(self):
        self.new_project()
        self.cst_file['type'] = 'DS'

    def open(self, path):
        self.cst_file = json.loads(Path(path).read_text())

    def save(self, path, **kwargs):
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        Path(path).write_text(json.dumps(self.cst_file), encoding='utf-8')

    def close(self):
        self.project.close()
