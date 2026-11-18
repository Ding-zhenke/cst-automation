"""Bind installed VBA templates using CST 2026.1 project resources."""
from contextlib import contextmanager
import hashlib
import os
from pathlib import Path
import struct
from tempfile import NamedTemporaryFile
import zlib

from cst_automation.builtin_templates import append_index, component, prepare, settings_resource
from cst_automation.result_templates import ResultTemplateError
from cst_automation.template_registration import SUPPORTED_NATIVE_VERSION
from cst_solver.circuit.native import _task


@contextmanager
def registration_lock(project):
    """Exclude other registrations across the native save/close/reopen interval."""
    lock = project.with_suffix('.cst.template-lock')
    temporary = getattr(os, 'O_TEMPORARY', 0)
    try:
        fd = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY | temporary, 0o600)
    except FileExistsError as exc:
        raise ResultTemplateError('Template registration is already in progress') from exc
    try:
        yield
    finally:
        os.close(fd)
        if not temporary:
            lock.unlink()


def _archived(path, wanted):
    """Read just the requested native resource entries; CST alone writes the archive."""
    found = {}
    with path.open('rb') as stream:
        while True:
            sig = stream.read(4)
            if sig == b'DE\x01\x02':
                return found
            if sig != b'DE\x03\x04':
                raise ResultTemplateError('Unrecognized native CST project archive')
            head = stream.read(30)
            if len(head) != 30:
                raise ResultTemplateError('Truncated native CST archive header')
            method = struct.unpack_from('<H', head, 4)[0]
            crc, packed, size, n, extra = struct.unpack_from('<IIIHH', head, 14)
            key = stream.read(n).replace(b'\\', b'/')
            stream.seek(extra, 1)
            if key not in wanted:
                stream.seek(packed, 1)
                continue
            if key in found or method not in (0, 8):
                raise ResultTemplateError('Duplicate or unsupported archived template resource')
            data = stream.read(packed)
            raw = zlib.decompress(data, -15) if method == 8 else data
            if len(raw) != size or zlib.crc32(raw) != crc:
                raise ResultTemplateError('Damaged archived template resource')
            found[key] = raw


def add_builtin_result_template(app, category, name, *, settings, result_name=None,
                                post_task=None, create_post_task=False, result_type=None,
                                evaluation_type=None, tree_references=None):
    """Register a step and save/reopen the owned idle project. Never evaluate it."""
    result = component(name if result_name is None else result_name)
    if type(create_post_task) is not bool or (not post_task and create_post_task):
        raise ResultTemplateError('create_post_task requires an explicit DS post_task')
    if post_task is not None:
        for part in post_task.split('\\'):
            component(part)
    if tree_references is not None and not isinstance(tree_references, dict):
        raise ResultTemplateError('tree_references must map setting names to native tree paths')
    refs = dict(tree_references or {})
    context = 'DS' if post_task else 'MWS'
    prj = app.cst_file
    schematic = prj.schematic
    install = schematic.GetInstallPath()
    if not install:
        raise ResultTemplateError('Could not locate the CST installation')
    file, source, values, kind, mode = prepare(Path(install)/'Library'/'Result Templates',
        category, name, settings, context, result_type, evaluation_type)
    title = file.stem.partition('^')[0]
    touchstone_ds = post_task and title == '- Touchstone Export' and category.casefold() == 's-parameters'
    if touchstone_ds:
        if refs:
            raise ResultTemplateError('Touchstone Export takes its tree reference from TaskName')
        refs['TaskName'] = 'Tasks\\' + settings['TaskName']
    # Validate names/references and settings before any native task creation.
    append_index(None, result, title, category, file.name, kind, mode, refs)
    path = Path(prj.filename()).resolve()
    root = Path(prj.folder()).resolve()
    if not path.is_file() or path.suffix.lower() != '.cst' or root != path.with_suffix(''):
        raise ResultTemplateError('An explicitly saved CST project and companion directory are required')
    if str(schematic.GetApplicationVersion()) != SUPPORTED_NATIVE_VERSION:
        raise ResultTemplateError('Unsupported CST native template resource version')
    if schematic.GetActivePostprocessingTask():
        raise ResultTemplateError('Native post-processing is active')
    if not post_task and (prj.model3d is None or prj.project_type().name != 'MWS'):
        raise ResultTemplateError('An MWS project is required for a project-level result template')
    if prj.model3d is not None and prj.model3d.is_solver_running():
        raise ResultTemplateError('The 3D solver is active')
    if touchstone_ds:
        _task(schematic, settings['TaskName'], 's-parameters')
    if post_task:
        task = _task(schematic, post_task, 'template', create=create_post_task)
        generic = Path(task.GetModelFolder(True)).resolve()
        parent = root/'Model'/'DS'
        folders = [p for p in parent.glob(generic.name + '_*') if p.is_dir()]
        if generic.parent != parent or len(folders) != 1 or folders[0].resolve().parent != parent:
            raise ResultTemplateError('Could not identify the materialized native Post-Processing task folder')
        folder, index_name = folders[0], 'Summary.rpp'
    else:
        folder, index_name = root/'Model'/'3D', 'Model.rpp'
    if folder.resolve() != folder or not folder.is_dir():
        raise ResultTemplateError('Invalid native template directory')
    index = folder/index_name
    module = folder/(result + ('.r0d' if '0D' in kind else '.r1d'))
    if index.resolve() != index or module.resolve() != module:
        raise ResultTemplateError('Redirected template resource')
    def key(p):
        return p.relative_to(root).as_posix().encode()
    requested = {key(index), key(module)}
    prior = _archived(path, requested)
    original = index.read_bytes() if index.exists() else None
    if original is None and key(index) in prior:
        raise ResultTemplateError('Existing archived index is not materialized in the open project')
    if key(index) in prior and original != prior[key(index)]:
        raise ResultTemplateError('Current and saved template lists differ; save the current project first')
    if module.exists() or key(module) in prior:
        raise ResultTemplateError('Template resource already exists: ' + result)
    new_index, encoded = append_index(original, result, title, category, file.name, kind, mode, refs)
    resource = settings_resource(source, {**values, **encoded})
    # The new resource is exclusive. Publish its index last, preserving prior rows.
    tmp = NamedTemporaryFile(dir=folder, delete=False)
    staged = Path(tmp.name)
    try:
        with tmp:
            tmp.write(new_index)
        with module.open('xb') as stream:
            try:
                stream.write(resource)
            except OSError:
                stream.close()
                module.unlink()
                raise
        try:
            if (index.read_bytes() if index.exists() else None) != original:
                raise ResultTemplateError('Template index changed during registration')
            staged.replace(index)
        except BaseException:
            module.unlink()
            raise
    finally:
        staged.unlink(missing_ok=True)
    app.save(str(path), allow_overwrite=True)
    if _archived(path, requested) != {key(index): new_index, key(module): resource}:
        raise ResultTemplateError('CST save did not persist the requested registration; inspect the project before retry')
    prj.close()
    app.cst_file = None
    app.open(str(path))
    if not index.is_file() or index.read_bytes() != new_index or module.read_bytes() != resource:
        raise ResultTemplateError('Native reopen did not restore the template registration')
    return dict(category=category, name=name, result_name=result, result_type=kind,
                post_task=post_task, settings=dict(settings), tree_references=refs,
                project_path=str(path), template_file=file.name, source_sha256=hashlib.sha256(source).hexdigest(),
                saved=True, reopen_verified=True, registration_persistence_verified=True,
                template_execution_verified=False)
