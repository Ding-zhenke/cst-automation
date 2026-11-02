"""Explicit conversation session tools; no process-global current session."""
from .errors import tool_payload


def register_session_tools(root, *, backend='cst', replace=False):
    from tpc_service.sessions import SessionManager
    from .tools import register_tool, _spec
    manager = SessionManager(root, backend=backend)
    string = {'type': 'string', 'minLength': 1}
    identity = {'session_id': string, 'credential': string}

    def ensure(a):
        return tool_payload({'session': manager.ensure(a['binding'], a['request_id'])},
                            notes=['Save this private recovery reference separately for this conversation. No CST started.'])

    def status(a):
        return tool_payload({'session': manager.status(a['session_id'], a['credential'])})

    def submit(a):
        return tool_payload({'job': manager.submit(a['session_id'], a['credential'], a['request_id'],
                            a['operation'], a.get('params'), operation_id=a.get('operation_id'))},
                            notes=['Accepted asynchronously; timeout/disconnection does not cancel or requeue the original operation.'])

    def job(a):
        return tool_payload({'job': manager.job(a['session_id'], a['credential'], a['job_id'])})

    def resume(a):
        return tool_payload({'session': manager.resume(a['session_id'], a['credential'])})

    def close(a):
        return tool_payload({'job': manager.close(a['session_id'], a['credential'], a['request_id'])})

    def reconcile(a):
        return tool_payload({'session': manager.reconcile(a['session_id'], a['credential'],
                            a['review_note'], a['project_digests'], confirm_idle=a.get('confirm_idle', False),
                            environment_identity=a.get('environment_identity'),
                            confirm_no_environment=a.get('confirm_no_environment', False),
                            abandon_projects=a.get('abandon_projects'))})

    entries = [
        ('ensure_cst_session', 'Allocate an independent conversation binding without starting CST.',
         {'binding': string, 'request_id': string}, ['binding', 'request_id'], ensure, False),
        ('get_cst_session', 'Read the explicit session and durable task state.', identity,
         list(identity), status, True),
        ('submit_cst_session_operation', 'Queue an explicit operation in the bound persistent CST environment. Geometry requires prior reviewed preview.',
         dict(identity, request_id=string, operation={'type': 'string', 'enum': [
             'start', 'create_project', 'import_project', 'inspect', 'history', 'set_parameters', 'solve', 'circuit']},
              params={'type': 'object'}, operation_id=string),
         list(identity) + ['request_id', 'operation'], submit, False),
        ('get_cst_session_job', 'Read an existing receipt; never repeat a write because a client wait timed out.',
         dict(identity, job_id=string), list(identity) + ['job_id'], job, True),
        ('resume_cst_session', 'Reconnect the owned worker. Uncertain mutations remain fenced pending reconciliation.',
         identity, list(identity), resume, False),
        ('close_cst_session', 'Explicitly save and close only this conversation environment after accepted work drains.',
         dict(identity, request_id=string), list(identity) + ['request_id'], close, False),
        ('reconcile_cst_session', 'Only after explicit human scene review: adopt reviewed saved files without replay or certifying unknown operations. Never call automatically.',
         dict(identity, review_note=string, project_digests={'type': 'object'},
              confirm_idle={'type': 'boolean'}, environment_identity={'type': 'object'},
              abandon_projects={'type': 'array', 'items': {'type': 'string'}},
              confirm_no_environment={'type': 'boolean'}),
         list(identity) + ['review_note', 'project_digests', 'confirm_idle'], reconcile, False),
    ]
    for name, description, properties, required, handler, readonly in entries:
        register_tool(name, _spec(name, description, properties, required, read_only=readonly),
                      handler, replace=replace)
