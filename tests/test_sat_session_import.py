from types import SimpleNamespace
import pytest
from cst_solver.import_export.io import IOMixin
from tpc_service.errors import ServiceError
from tpc_service.sessions.model_api import dispatch


def sink():
    h=[]
    a=IOMixin()
    a.cst_file=SimpleNamespace(model3d=SimpleNamespace(add_to_history=lambda *x:h.append(x)))
    return a,h


@pytest.mark.parametrize('tpn',[False,"False"])
def test_scaled_import(tmp_path,tpn):
    p=tmp_path/'source.sat';p.write_text('test')
    a,h=sink()
    dispatch(a,[{'method':'import_sat','args':[str(p)],'kwargs':{'tpn':tpn,'scale_to_unit':True}}])
    assert '.ScaleToUnit "True"' in h[0][1]
    assert '.TypePECForNewMaterials "False"' in h[0][1]


def test_old_defaults():
    a,h=sink();a.import_sat('source.sat')
    assert '.ScaleToUnit "0"' in h[0][1]
    assert '.TypePECForNewMaterials "True"' in h[0][1]


@pytest.mark.parametrize('bad',[{'scale_to_unit':'True'},{'tpn':0},{'tpn':'arbitrary'},{'filename':'relative.sat'},{'filename':'C:/missing.sat'}])
def test_fail_before_earlier_write(tmp_path,bad):
    p=tmp_path/'source.sat';p.write_text('test')
    k=dict(filename=str(p),tpn=False,scale_to_unit=True);k.update(bad)
    a=SimpleNamespace(new_component=lambda *x:pytest.fail('Earlier write'))
    with pytest.raises(ServiceError):
        dispatch(a,[{'method':'new_component','args':['never']},{'method':'import_sat','kwargs':k}])


def test_wrong_suffix(tmp_path):
    p=tmp_path/'source.step';p.write_text('test')
    with pytest.raises(ServiceError):
        dispatch(sink()[0],[{'method':'import_sat','args':[str(p)]}])
