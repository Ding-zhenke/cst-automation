"""Project-owned immutable attempt journal; no solver or filesystem archive actions."""
import hashlib
import json
import sqlite3
from pathlib import Path

STAGES = ('em', 'static_sp', 'ads_hb', 'analysis')
INPUTS = ('geometry', *STAGES)


def _json(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False)


def _id(value):
    if not isinstance(value, str) or not value.strip() or len(value) > 256:
        raise ValueError('Nonempty bounded identifier required')
    return value


def identities(inputs):
    if not isinstance(inputs, dict) or set(inputs) != set(INPUTS) or any(not isinstance(inputs[k], dict) for k in INPUTS):
        raise ValueError('Exact geometry, em, static_sp, ads_hb and analysis objects required')
    deps = {'em': ('geometry', 'em'), 'static_sp': ('geometry', 'em', 'static_sp'),
            'ads_hb': ('geometry', 'em', 'ads_hb'), 'analysis': INPUTS}
    return {stage: hashlib.sha256(_json({k: inputs[k] for k in keys}).encode('utf-8')).hexdigest()
            for stage, keys in deps.items()}


class DesignState:
    def __init__(self, path):
        self.path = str(Path(path).absolute())
        with self._connect() as db:
            db.executescript('''
                CREATE TABLE IF NOT EXISTS projects (id TEXT PRIMARY KEY, path TEXT NOT NULL, topology TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS attempts (id TEXT PRIMARY KEY, project TEXT NOT NULL, candidate TEXT NOT NULL,
                    inputs TEXT NOT NULL, identities TEXT NOT NULL, FOREIGN KEY(project) REFERENCES projects(id));
                CREATE TABLE IF NOT EXISTS stages (attempt TEXT NOT NULL, stage TEXT NOT NULL, request TEXT NOT NULL,
                    status TEXT NOT NULL, receipt TEXT, PRIMARY KEY(attempt,stage), FOREIGN KEY(attempt) REFERENCES attempts(id));
            ''')

    def _connect(self):
        db = sqlite3.connect(self.path, timeout=30)
        db.execute('PRAGMA foreign_keys=ON')
        return db

    def register_project(self, project_id, cst_path, topology_digest):
        project_id, topology_digest = _id(project_id), _id(topology_digest)
        if not isinstance(cst_path, str) or not Path(cst_path).is_absolute():
            raise ValueError('Absolute working CST path required')
        with self._connect() as db:
            db.execute('INSERT OR IGNORE INTO projects VALUES (?,?,?)', (project_id, cst_path, topology_digest))
            if db.execute('SELECT path,topology FROM projects WHERE id=?', (project_id,)).fetchone() != (cst_path, topology_digest):
                raise ValueError('Project path or topology differs; create a distinct project identity')

    def begin_attempt(self, project_id, candidate_id, attempt_id, inputs):
        project_id, candidate_id, attempt_id = map(_id, (project_id, candidate_id, attempt_id))
        data, basis = _json(inputs), _json(identities(inputs))
        with self._connect() as db:
            db.execute('INSERT OR IGNORE INTO attempts VALUES (?,?,?,?,?)', (attempt_id, project_id, candidate_id, data, basis))
            if db.execute('SELECT project,candidate,inputs,identities FROM attempts WHERE id=?', (attempt_id,)).fetchone() != (project_id, candidate_id, data, basis):
                raise ValueError('Attempt identity already bound to different inputs')
        return json.loads(basis)

    def reserve(self, attempt_id, stage, request_id):
        _id(attempt_id); _id(request_id)
        if stage not in STAGES:
            raise ValueError('Unknown stage')
        with self._connect() as db:
            db.execute('BEGIN IMMEDIATE')
            row = db.execute('SELECT request,status FROM stages WHERE attempt=? AND stage=?', (attempt_id, stage)).fetchone()
            if row:
                if row[0] != request_id:
                    raise ValueError('Stage already reserved; inspect original request')
                return {'request_id': row[0], 'status': row[1], 'new': False}
            if not db.execute('SELECT 1 FROM attempts WHERE id=?', (attempt_id,)).fetchone():
                raise ValueError('Unknown attempt')
            db.execute('INSERT INTO stages VALUES (?,?,?,?,NULL)', (attempt_id, stage, request_id, 'reserved'))
            return {'request_id': request_id, 'status': 'reserved', 'new': True}

    def finish(self, attempt_id, stage, request_id, status, receipt):
        if status not in ('complete', 'failed') or not isinstance(receipt, dict) or not receipt:
            raise ValueError('Explicit terminal status and receipt required')
        data = _json(receipt)
        with self._connect() as db:
            db.execute('BEGIN IMMEDIATE')
            row = db.execute('SELECT request,status,receipt FROM stages WHERE attempt=? AND stage=?', (attempt_id, stage)).fetchone()
            if not row or row[0] != request_id:
                raise ValueError('Matching reservation required')
            if row[1] != 'reserved':
                if row[1:] == (status, data):
                    return
                raise ValueError('Terminal outcome cannot be overwritten')
            db.execute('UPDATE stages SET status=?,receipt=? WHERE attempt=? AND stage=?', (status, data, attempt_id, stage))

    def snapshot(self, attempt_id):
        with self._connect() as db:
            row = db.execute('SELECT project,candidate,inputs,identities FROM attempts WHERE id=?', (attempt_id,)).fetchone()
            if not row:
                raise ValueError('Unknown attempt')
            stages = db.execute('SELECT stage,request,status,receipt FROM stages WHERE attempt=?', (attempt_id,)).fetchall()
        return {'project_id': row[0], 'candidate_id': row[1], 'inputs': json.loads(row[2]),
                'identities': json.loads(row[3]), 'stages': {s: {'request_id': r, 'status': st,
                'receipt': json.loads(receipt) if receipt is not None else None} for s, r, st, receipt in stages}}
