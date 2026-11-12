"""Release only a fully reviewed static-preparation failure fence."""
from pathlib import Path
from tpc_service.errors import ServiceError
from .job_index import JobIndex
from .native import Runtime, file_digest
from .store import alive, assert_environment_unclaimed, digest, identifier, lock, read, write


def accept(manager,session_id,credential,*,failed_job_id,run_job_id,read_job_id,project_digests,
           environment_identity,review_note,confirm_idle=False):
    def require(value,message):
        if not value: raise ServiceError('session_static_finalize_refused',message)
    for value in (failed_job_id,run_job_id,read_job_id): identifier(value)
    require(confirm_idle is True and isinstance(review_note,str) and 0<len(review_note.strip())<=8192,
            'Explicit idle and review note required')
    require(isinstance(project_digests,dict) and project_digests,'All project digests required')
    folder=manager._folder(session_id)
    with lock(manager.root/'registry.lock'),lock(folder/'state.lock'):
        state=manager._state(folder,credential)
        previous=state.get('last_resolution') or {}
        if state.get('status')=='ready' and previous.get('kind')=='completed_static_recovery':
            require(previous.get('failed_job_id')==failed_job_id and previous.get('run_job_id')==run_job_id
                    and previous.get('read_job_id')==read_job_id and previous.get('project_digests')==project_digests
                    and previous.get('environment_identity')==environment_identity and previous.get('review_note')==review_note
                    and state.get('environment')==environment_identity and alive(environment_identity)
                    and set(project_digests)==set(state.get('projects',{}))
                    and all(file_digest(project['path'])==project_digests[pid] for pid,project in state['projects'].items()),
                    'Existing static resolution inputs differ')
            return dict(previous,status='ready')
        require(manager.backend==state.get('backend')=='cst' and state.get('status')=='needs_reconcile'
                and not state.get('worker_upgrade') and not state.get('uncertain_jobs')
                and not state.get('launch_intent') and not state.get('close_requested')
                and not JobIndex.load(folder).active_jobs(), 'Exact idle failure fence required')
        require(state.get('environment')==environment_identity and alive(environment_identity)
                and state.get('worker') and alive(state['worker'])
                and 'static-sp-guarded-run-v1' in state.get('worker_capabilities',[]),
                'Exact live DE and guarded worker required')
        assert_environment_unclaimed(manager.root,session_id,environment_identity)
        require(set(project_digests)==set(state.get('projects',{})), 'All registered projects must be reviewed')
        try:
            for pid,project in state['projects'].items():
                require(project.get('saved') is True and file_digest(project['path'])==project_digests[pid]
                        and project.get('saved_digest')==project_digests[pid], 'Registered saved project differs')
            original=read(folder/'jobs'/(failed_job_id+'.json')) or {}
            run=read(folder/'jobs'/(run_job_id+'.json')) or {};out=run.get('result') or {}
            reading=read(folder/'jobs'/(read_job_id+'.json')) or {};result=reading.get('result') or {}
            handoff=state.get('last_worker_upgrade') or {};partial=handoff.get('static_partial') or {}
            project_id=original.get('params',{}).get('project_id')
            require(original.get('job_id')==failed_job_id and original.get('session_id')==session_id
                    and original.get('status')=='failed' and original.get('operation')=='prepare_static_sp'
                    and original.get('error')==state.get('last_error') and partial.get('failed_job_digest')==digest(original)
                    and partial.get('failed_job_id')==failed_job_id and partial.get('project_id')==project_id,
                    'Original failure differs')
            require(handoff.get('phase')=='complete' and handoff.get('return_to_fence') is True
                    and handoff.get('environment')==environment_identity and handoff.get('new_worker')==state.get('worker'),
                    'Reviewed worker handoff differs')
            require(run.get('job_id')==run_job_id and run.get('session_id')==session_id and run.get('status')=='succeeded'
                    and run.get('operation')=='run_fenced_static_sp' and run.get('params',{}).get('project_id')==project_id
                    and run.get('params',{}).get('failed_job_id')==failed_job_id
                    and run.get('params',{}).get('exclude_job_id')==out.get('exclude_job_id')
                    and run.get('params',{}).get('impedance_job_id')==out.get('impedance_job_id')
                    and run.get('params',{}).get('confirm_run') is True
                    and out.get('original_failed_job_id')==failed_job_id and out.get('saved') is True
                    and out.get('saved_digest')==project_digests.get(project_id) and out.get('solver_verified') is True
                    and out.get('actual_grid_verified') is True and out.get('structural_no_em_dependency_verified') is True
                    and out.get('3d_files_unchanged') is True and out.get('3d_log_unchanged') is True,
                    'Verified matching static run required')
            native=out.get('circuit_outcome') or {}
            require(native.get('status')=='succeeded' and native.get('submitted') is True
                    and native.get('execution_returned') is True and native.get('update_call_state')=='returned'
                    and native.get('saved') is True and native.get('saved_digest')==project_digests.get(project_id)
                    and native.get('task_name')==out.get('task_name') and native.get('mode')=='network'
                    and native.get('run_token')==out.get('run_token') and bool(native.get('run_token'))
                    and (native.get('execution_evidence') or {}).get('completed') is True,
                    'Native target-task run receipt is incomplete')
            require(reading.get('job_id')==read_job_id and reading.get('session_id')==session_id
                    and reading.get('status')=='succeeded' and reading.get('operation')=='read_fenced_static_sp'
                    and reading.get('params',{}).get('project_id')==project_id
                    and reading.get('params',{}).get('failed_job_id')==failed_job_id
                    and reading.get('params',{}).get('run_job_id')==run_job_id
                    and reading.get('params',{}).get('expected_saved_digest')==project_digests[project_id]
                    and reading.get('params',{}).get('positive_run_id')==result.get('positive_run_id')
                    and reading.get('params',{}).get('confirm_idle') is True
                    and result.get('original_failed_job_id')==failed_job_id and result.get('run_job_id')==run_job_id
                    and result.get('saved_digest')==project_digests[project_id] and result.get('current_content_matches_positive') is True
                    and type(result.get('positive_run_id')) is int and result['positive_run_id']>0,
                    'Matching positive-ID read required')
            root=(folder/'static_sp_runs'/run_job_id).resolve()
            for key,prefix in (('current_curves_path','current_curves_sha256'),('positive_curves_path','positive_curves_sha256')):
                item=out if key.startswith('current') else result
                path=Path(item[key]).resolve()
                require(path.is_relative_to(root) and path.is_file() and file_digest(path)==item[prefix],
                        'Archived complex curves changed')
            excluded=read(folder/'jobs'/(identifier(out.get('exclude_job_id'))+'.json')) or {}
            expected=(excluded.get('result') or {}).get('after')
            require(excluded.get('operation')=='exclude_unconnected_self_em' and excluded.get('status')=='succeeded'
                    and excluded.get('params',{}).get('project_id')==project_id and isinstance(expected,dict)
                    and digest(expected)==run.get('params',{}).get('snapshot_digest'), 'Excluded circuit receipt differs')
        except (OSError,KeyError,ValueError,TypeError) as exc:
            raise ServiceError('session_static_finalize_refused','Receipt or saved artifact unavailable') from exc
        from .native_handoff import verify_native
        runtime=Runtime(folder,'cst');verify_native(runtime,state)
        handle=runtime.handles.get(project_id)
        require(handle is not None and runtime.app is not None, 'Exact native project handle missing')
        runtime.app.cst_file=handle
        from cst_solver.circuit.adapter import NativeAdapter
        require(NativeAdapter(runtime.app).inspect()==expected, 'Native circuit changed since run')
        require(alive(environment_identity) and all(file_digest(project['path'])==project_digests[pid]
                for pid,project in state['projects'].items()), 'Native identity or saved projects changed')
        import time
        audit={'kind':'completed_static_recovery','failed_job_id':failed_job_id,'run_job_id':run_job_id,
               'read_job_id':read_job_id,'project_digests':dict(project_digests),'environment_identity':environment_identity,
               'review_note':review_note,'positive_run_id':result['positive_run_id'],'original_failure_preserved':True,
               'positive_fresh_attribution_verified':False,'formal_hb_gate_satisfied':False,
               'source_qualification':'not_assessed','human_reviewed':True,'readback_verified':False,
               'solver_verified':False,'at':time.time()}
        state.update(status='ready',last_error=None,last_resolution=audit)
        write(folder/'session.json',state)
        return dict(audit,status='ready')
