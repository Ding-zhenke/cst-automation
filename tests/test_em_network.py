"""No live CST: native fitting/updates and service rejection contracts."""
from pathlib import Path
from types import SimpleNamespace
import copy
import hashlib
import pytest

from test_workflow_enforcement import setup, prepare_em_evidence, submit, runtime_for, hb, native_app
from tpc_service.sessions.store import read,write
from tpc_service.errors import ServiceError
from cst_solver.circuit.em_network import MOR, digest


def fit_params(project, em='em'):
    d=project.with_suffix('')/'Export'/'ABCD'
    return dict(project_id='p',em_job_id=em,block_name='EM',expected_type='CSTMWS',expected_ports=['1','2'],
        settings=dict(fmax=3,accuracy_abs=.01,enhance_dc=True,passivate=True,method='BUILT-IN',
                      error_norm='Max',natural_impedances=False,reference_ohm=75),
        export_paths={k:str(d/('EM_'+k+'.csv' if k!='log' else 'EM.log')) for k in ('A','B','C','D','log')})


def matrix(path, n=2):
    row=' '.join(['0']*(2*n*n))
    path.write_text('# GHz S RI R 75\n0 '+row+'\n3 '+row+'\n')


class Block:
    def __init__(self,p):
        self.p=p;self.kind=p['expected_type'];self.ports=p['expected_ports'][:]
        self.file='';self.cache=False;self.writes=[];self.values=dict(p.get('settings',{}))
        self.extracts=0
        for key,(setter,getter) in MOR.items():
            setattr(self,getter,lambda key=key:self.values[key])
            setattr(self,setter,lambda value,key=key:self.set_value(key,value))
    def set_value(self,key,value):self.writes.append(key);self.values[key]=value
    def DoesExist(self):return True
    def GetTypeName(self):return self.kind
    def GetNumberOfPorts(self):return len(self.ports)
    def GetPortName(self,i):return self.ports[i]
    def GetFile(self):return self.file
    def GetNumberOfFiles(self):return 1
    def IsCachingFiles(self):return self.cache
    def CanUseMOR(self):return True
    def ExtractStateSpaceModel(self,fmax,task):
        assert task=='';self.extracts+=1
        for file in self.p['export_paths'].values():
            p=Path(file);p.parent.mkdir(parents=True,exist_ok=True);p.write_text('synthetic native export')
    def SetFile(self,path):self.writes.append('SetFile');self.file=path


def app_for(block):
    app=native_app()
    app.circuit.adapter.select=lambda *a:block
    return app


@pytest.mark.parametrize('change', [dict(expected_type='Touchstone file'),dict(expected_ports=['1','1']),
    dict(settings={}),dict(em_job_id=''),dict(block_name='../bad')])
def test_invalid_fit_does_not_launch(setup,change):
    p=fit_params(setup[3]);p.update(change)
    with pytest.raises(ServiceError):submit(setup,'fit_em_network',{k:v for k,v in p.items() if k!='project_id'})
    assert not setup[-1]


def test_unbound_fit_does_not_launch(setup):
    p=fit_params(setup[3])
    with pytest.raises(ServiceError) as e:submit(setup,'fit_em_network',{k:v for k,v in p.items() if k!='project_id'})
    assert e.value.code=='workflow_required' and not setup[-1]


@pytest.mark.parametrize('failure',['external','wrong_ports','missing_getter','old_exports'])
def test_native_fit_rejects_before_mutation(tmp_path,failure):
    from cst_solver.circuit.em_network import fit
    p=fit_params(tmp_path/'model.cst');b=Block(p)
    if failure=='external':b.file=str(tmp_path/'external.cst')
    if failure=='wrong_ports':b.ports.reverse()
    if failure=='missing_getter':delattr(b,'GetMOR_ErrorNorm')
    if failure=='old_exports':
        old=Path(p['export_paths']['A']);old.parent.mkdir(parents=True);old.write_text('keep')
        p['export_paths']['A']=str(old.with_name('EM_A_new.csv'))
    with pytest.raises((ValueError,AttributeError)):fit(app_for(b),p,tmp_path/'model.cst')
    assert not b.writes and b.extracts==0


def fitted(setup):
    from tpc_service.sessions.operations import execute
    runtime,em,analysis,artifact=prepare_em_evidence(setup)
    p=fit_params(setup[3],em['job_id']);b=Block(p);app=app_for(b)
    runtime.project=lambda *_:(app,runtime.state()['projects']['p'])
    job=submit(setup,'fit_em_network',{k:v for k,v in p.items() if k!='project_id'},'fit')
    result=execute(runtime,job)
    job.update(status='succeeded',result=result);write(setup[2]/'jobs'/(job['job_id']+'.json'),job)
    return runtime,em,analysis,job,b,app


def prepared_update(setup):
    from tpc_service.sessions.operations import execute
    runtime,em,analysis,fitjob,b,app=fitted(setup)
    new=setup[2]/'fitted.s2p';matrix(new)
    old=setup[2]/'old.s2p';matrix(old)
    b.kind='Touchstone file';b.file=str(old)
    p=dict(project_id='p',em_job_id=em['job_id'],fit_job_id=fitjob['job_id'],block_name='HBInput',
        expected_type='Touchstone file',expected_ports=['1','2'],expected_file_sha256=digest(old),
        path=str(new),sha256=digest(new),reference_ohm=75,fmax_hz=3e9,max_fit_error=.01)
    report=read(analysis)
    report['metrics']['mor_fit_max_abs_error']=.001
    report['artifacts']+=fitjob['result']['artifacts']+[{'path':str(new),'sha256':digest(new)}]
    write(analysis,report)
    accept=submit(setup,'accept_workflow_evidence',{'em_job_id':em['job_id'],'report_path':str(analysis)},'accept')
    execute(runtime,accept)
    return runtime,p,b,app


def test_fit_keeps_em_generation_and_blocks_hb_until_updated(setup):
    runtime,em,analysis,job,b,app=fitted(setup)
    w=runtime.state()['projects']['p']['workflow']
    assert w['em_receipt']['job_id']==em['job_id'] and w['em_generation']==w['network_fit']['em_generation']
    assert b.extracts==1 and job['result']['dc_verified'] is False
    assert w['network_required'] and w['network_update'] is None


def test_update_then_hb_checks_actual_file(setup,monkeypatch):
    from tpc_service.sessions import operations
    runtime,p,b,app=prepared_update(setup)
    job=submit(setup,'update_hb_network',{k:v for k,v in p.items() if k!='project_id'},'update')
    result=operations.execute(runtime,job)
    job.update(status='succeeded',result=result);write(setup[2]/'jobs'/(job['job_id']+'.json'),job)
    calls=[]
    # Source/load assertions still run: restore the generic native property check.
    b.GetProperty=lambda *_:75
    monkeypatch.setattr(operations,'circuit',lambda *a:calls.append('HB') or {'ok':True})
    hbjob=hb(setup)
    assert operations.execute(runtime,hbjob)=={'ok':True} and calls==['HB']
    b.file=str(setup[2]/'old.s2p')
    calls.clear()
    with pytest.raises(ServiceError):operations.execute(runtime,hbjob)
    assert not calls


@pytest.mark.parametrize('failure',['order','changed','missing_fit_artifact','bad_error','stale_generation'])
def test_update_preflight_never_launches_on_bad_input(setup,failure):
    runtime,p,b,app=prepared_update(setup)
    if failure=='order':p['expected_ports'].reverse()
    if failure=='changed':Path(p['path']).write_text('changed')
    if failure in ('missing_fit_artifact','bad_error'):
        state=runtime.state();w=state['projects']['p']['workflow'];path=w['evidence']['report_path'];report=read(path)
        if failure=='missing_fit_artifact':report['artifacts']=[a for a in report['artifacts'] if not a['path'].endswith('EM_A.csv')]
        else:report['metrics']['mor_fit_max_abs_error']=1
        write(path,report)
    if failure=='stale_generation':
        from tpc_service.sessions.workflow import invalidate
        invalidate(runtime,dict(operation='solve',params={'project_id':'p'}))
    setup[-1].clear()
    with pytest.raises(ServiceError):submit(setup,'update_hb_network',{k:v for k,v in p.items() if k!='project_id'},'bad-update')
    assert not setup[-1] and 'SetFile' not in b.writes


@pytest.mark.parametrize('bad',['missing_dc','nan','incomplete','wrong_ref','reverse'])
def test_bad_touchstone_rejected(tmp_path,bad):
    from cst_automation.em_network import touchstone
    p=tmp_path/'data.s2p';matrix(p);s=p.read_text()
    if bad=='missing_dc':s=s.replace('\n0 ','\n1 ')
    if bad=='nan':s=s.replace('0 0','nan 0',1)
    if bad=='incomplete':s=s.rstrip().rsplit(' ',1)[0]+'\n'
    if bad=='wrong_ref':s=s.replace('R 75','R 50')
    if bad=='reverse':s=s+'1 '+' '.join(['0']*8)+'\n'
    p.write_text(s)
    with pytest.raises(ValueError):touchstone(p,2,75,3e9)
