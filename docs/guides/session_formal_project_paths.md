# Explicit formal project paths

The persistent session API retains the original session owner, worker,
environment, project ID and recovery reference when a formal filename is used.
These are operation parameters for the existing API:

```python
manager.submit(session_id, credential, request_id, operation, params=None,
               *, operation_id=None)
```

For a new empty project:

The examples use a caller-reviewed `formal_path` (`pathlib.Path`) with the
authorized task directory and formal filename; they do not infer a machine path.

```python
operation = 'create_project'
params = {
    'project_id': 'device',
    'project_type': 'MWS',  # or DS
    'working_path': str(formal_path.resolve()),  # caller-approved directory/name
    'authorize_working_path': True,
}
```

For an independent continuation copy, use `operation='import_project'` and
add `source_path` (existing absolute `.cst` or `.prj` file). The destination
is the exact authorized `.cst` filename; the source and its same-name paired
data directory remain unchanged. The copy includes paired data. Existing
destination files or paired data directories are rejected. An independent
copy of a source already registered within the session still requires
`copy_reason`, as before. Omitting `working_path` and its authorization keeps
the existing `projects/<project_id>/model.cst` default.

For explicitly authorized continuation of the saved formal file itself:

```python
operation = 'adopt_project'
params = {
    'project_id': 'device',
    'working_path': str(formal_path.resolve()),
    'authorize_working_path': True,
    'expected_digest': '<64 lowercase hexadecimal SHA-256 characters>',
    'review_note': 'Continue the reviewed saved formal baseline in place',
}
```

Adoption verifies the saved digest before opening and again afterward. It
does not copy, save, overwrite or delete the baseline. Its receipt has
`adopted=true`, `saved=false`; the project record describes the already-saved
baseline with `saved=true`, `saved_digest`, exact `path_authorization`, and
`adoption_review`. Subsequent normal edits/save/solve use this same formal
path. The digest identifies the saved CST file, not dependency closure,
native model correctness or solver validity.

Use the original request ID to retrieve the existing receipt after a lost
reply. Continue with the original project ID and recovery reference; do not
adopt/import it again. Saved-file changes outside the session remain subject
to normal digest/reconciliation checks. Adoption of a project already
registered to another session is rejected, including canonical path and
same-file aliases. Accepted queued operations also reserve the destination.
Claims are serialized within the same authorized session root, not across
arbitrary roots or external applications.
Failed project creation/import/adoption receipts retain their exact-path
claim even when native opening failed before a project record was written.
Only explicit scene reconciliation resolving that failed receipt releases
the claim; a changed session status alone does not establish that no tab
was opened. Registered projects continue to hold their claims afterward.

The existing explicit MCP tool `submit_cst_session_operation` accepts the
same `operation` and `params`; its operation enum includes `adopt_project`.
The CLI uses the existing `submit --operation adopt_project --params-file
<UTF-8 JSON>` entry point with the original `--root` and `--reference`.
There is no new global path setting, active-window lookup, implicit attach,
automatic cleanup, or DE shutdown.

Check that the worker has actually loaded the updated implementation before
using new operations. Updating repository files does not reload an existing
worker's imported modules. Do not hot-reload during an active operation; the
owning conversation controls any later idle-worker recovery, retaining the
original DE, reference and saved baseline. This API does not move an active
project or change its path retroactively.

Offline regression tests cover exact filenames, authorization, overwrite
rejection, paired copy preservation, unchanged adoption, changed digest,
queued ownership claims, same-file aliases, and request deduplication.
Native CST opening, saving and recovery require separate acceptance in an
explicitly idle authorized session; these tests do not certify them.

## Circuit routing of a registered formal project

Session `circuit` operations reuse the registered project ID and canonical
path. For paths outside the session workdir, the stored authorization must
match the exact formal path and the create/import/adopt operation that
registered it. The trusted host passes that one project file to the circuit
handler; request JSON cannot introduce this grant. The generic circuit service
keeps its workdir-only project rule when no trusted grant is provided.

This allows existing inspect/run_task/read_results routing for the registered
formal file. It does not broaden destination, package, input-model or template
source paths: explicit paths remain inside the original session workdir. The
borrowed app does not close or replace the owning session environment.
Project saves and existing project-resource failure audits retain their
project-owned locations; the grant does not authorize arbitrary export paths.

No fresh leaf-task log remains a separate evidence gap even when spectra are
readable. An unchanged parent log's errors are historical; no new log segment
means completed=False, not proof of the leaf failing or succeeding. Fresh
errors still prevent completion, and result counts do not replace run evidence.
