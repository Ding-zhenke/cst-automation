"""Configuration-only resource registration on an explicitly owned app.

The native archive round-trip verifies persisted registration configuration.
The DS iterator is not an idle-context registration getter. No evaluation or
solver method belongs in this module.
"""
import json
from pathlib import Path
from uuid import uuid4

from cst_automation.result_templates import ResultTemplateError
from cst_automation.template_registration import (
    SUPPORTED_NATIVE_VERSION, prepare_python_result_registration,
    inspect_python_result_registration, check_registration_conflict, payload_digest,
)
from .adapter import CircuitError
from .native import _task, _chain_names, configure_hb_postprocessing_chain, inspect_hb_postprocessing_chain


def registration_folder(schematic, post_task, resources):
    """Discover the folder CST materialized; never invent its numeric suffix."""
    task = _task(schematic, post_task, 'template')
    generic = Path(task.GetModelFolder(True)).resolve()
    root = Path(resources).resolve()
    ds_root = (root / 'Model' / 'DS').resolve()
    if not ds_root.is_relative_to(root) or generic.parent != ds_root:
        raise ResultTemplateError('Native generic task folder does not belong to the explicit project')
    if not schematic.SelectTreeItem('Tasks\\' + post_task):
        raise ResultTemplateError('CST did not select the explicit Post task')
    folders = [p.resolve() for p in ds_root.glob(generic.name + '_*') if p.is_dir()]
    if (len(folders) != 1 or folders[0].parent != ds_root
            or not folders[0].name.startswith(generic.name + '_')):
        raise ResultTemplateError('Native Post resource folder is absent, ambiguous or redirected')
    return folders[0]


def register_python_result_template(app, parent_task, hb_task, post_task, template_source, *,
                                    result_name, template_name, group, result_type, settings,
                                    eval_type='single_run', create=False, conflict='error', expected_registration_sha256=None):
    """Import one registration and verify exact content after native extraction.

    ``app`` must be the caller's idle, session-owned app. This deliberately
    closes/reopens this project only; a session owner must refresh its cached
    handle afterwards (the registered service route does so even on failure).
    No template module is imported or called. Persistence is not execution.
    """
    payload = prepare_python_result_registration(template_source, result_name=result_name,
        template_name=template_name, group=group, result_type=result_type, settings=settings, eval_type=eval_type)
    _chain_names(parent_task, hb_task, post_task)
    if type(create) is not bool or conflict not in ('error', 'replace'):
        raise ResultTemplateError('Boolean create and explicit error/replace conflict policy required')
    if conflict == 'replace' and (not isinstance(expected_registration_sha256, str)
                                  or len(expected_registration_sha256) != 64):
        raise ResultTemplateError('Replacement requires the complete registration SHA-256')
    if conflict == 'error' and expected_registration_sha256 is not None:
        raise ResultTemplateError('Expected digest requires conflict=replace')
    path = Path(app.cst_file.filename()).resolve()
    resources = Path(app.cst_file.folder()).resolve()
    if path.suffix.lower() != '.cst' or not path.is_file() or resources != path.with_suffix(''):
        raise ResultTemplateError('An explicitly saved .cst with its own companion directory is required')
    s = app.cst_file.schematic
    version = str(s.GetApplicationVersion())
    if version != SUPPORTED_NATIVE_VERSION:
        raise ResultTemplateError('Unsupported native registration build: ' + version)
    if s.GetActivePostprocessingTask():
        raise ResultTemplateError('Cannot register during active native post-processing')
    _task(s, parent_task, 'parameter sweep'); _task(s, hb_task, 'spectral lines')
    task = s.SimulationTask; task.Reset(); task.Name(post_task)
    exists = bool(task.DoesExist())
    if create and exists:
        raise ResultTemplateError('Post task already exists; create=True refuses conflicts')
    if not create and not exists:
        raise ResultTemplateError('Post task missing; explicit create=True required')
    if create and conflict == 'replace':
        raise ResultTemplateError('A new Post task cannot replace an existing registration')
    # For an existing task, conflict preflight precedes enabling or reordering it.
    if exists:
        folder = registration_folder(s, post_task, resources)
        check_registration_conflict(folder, payload, conflict=conflict,
                                    expected_registration_sha256=expected_registration_sha256)
    audit_root = (path.parent / '.cst_automation_template_audits').resolve()
    if audit_root.parent != path.parent:
        raise ResultTemplateError('Audit directory is redirected outside the owned project directory')
    audit = audit_root / uuid4().hex
    audit.mkdir(parents=True)
    stage = 'configure_chain'
    report = {'project_path': str(path), 'post_task': post_task, 'native_version': version,
              'requested_eval_type': eval_type,
              'audit_path': str(audit / 'receipt.json'), 'saved': False,
              'registration_persistence_verified': False, 'reopen_verified': False,
              'binding_verified': False, 'native_template_enumeration_verified': False,
              'template_execution_verified': False, 'solver_verified': False}
    def receipt():
        (audit / 'receipt.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    receipt()
    try:
        configure_hb_postprocessing_chain(s, parent_task, hb_task, post_task, create=create)
        folder = registration_folder(s, post_task, resources)
        before = check_registration_conflict(folder, payload, conflict=conflict,
                                    expected_registration_sha256=expected_registration_sha256)
        stage = 'write_registration'
        # Retain exact old bytes for recoverability before replacing any file.
        originals = audit / 'before'; originals.mkdir()
        for name in payload:
            target = folder / name
            if target.resolve().parent != folder:
                raise ResultTemplateError('Registration target escapes native task folder')
            if target.is_file(): (originals / name).write_bytes(target.read_bytes())
        # Commit the index last. Native evaluation is not active in this operation.
        for name in [n for n in payload if n != 'Summary.rpp'] + ['Summary.rpp']:
            temporary = folder / (name + '.' + uuid4().hex + '.tmp')
            temporary.write_bytes(payload[name]); temporary.replace(folder / name)
        expected, manifest = payload_digest(payload)
        current = inspect_python_result_registration(folder)
        if current['registration_sha256'] != expected:
            raise ResultTemplateError('Written registration content mismatch')
        report.update(registration=current, before_registration=before, manifest=manifest)
        stage = 'native_save'
        app.save(str(path), allow_overwrite=True)
        report['saved'] = True; receipt()
        stage = 'native_close'
        app.cst_file.close()
        if str(path).casefold() in {str(Path(p).resolve()).casefold() for p in app.project.list_open_projects()}:
            raise ResultTemplateError('Native project is still open after close')
        app.cst_file = None
        # Moving only this task's resources proves the subsequent read originates
        # from CST's saved archive rather than our earlier filesystem writes.
        stage = 'quarantine_owned_resources'
        backup = audit / 'saved_resources'
        folder.rename(backup)
        report['resource_backup'] = str(backup); receipt()
        stage = 'native_reopen_and_extract'
        app.open(str(path))
        s = app.cst_file.schematic
        reopened_folder = registration_folder(s, post_task, resources)
        restored = inspect_python_result_registration(reopened_folder)
        if restored['registration_sha256'] != expected:
            raise ResultTemplateError('Native archive did not restore the exact registration')
        chain = inspect_hb_postprocessing_chain(s, parent_task, hb_task, post_task)
        if not chain['readback_verified']:
            raise ResultTemplateError('Reopened native HB->Post chain differs')
        report.update(registration=restored, chain=chain, registration_persistence_verified=True,
                      reopen_verified=True, verification='native_archive_extraction_and_content_roundtrip',
                      stage='complete')
        receipt()
        return report
    except Exception as exc:
        report.update(stage=stage, error=repr(exc)); receipt()
        raise CircuitError('circuit_build_partial', 'Template registration interrupted: ' + str(exc),
                           stage=stage, registration_receipt=report) from exc
