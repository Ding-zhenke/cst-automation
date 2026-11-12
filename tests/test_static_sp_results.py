import copy
import pytest

from cst_automation.static_sp_results import verify_curves


def curves():
    return {key: {'tree_path': f'Tasks\\SP\\S-Parameters\\S{key[0]},{key[1]}',
                  'run_id': 3, 'parameters': {'L': '1'}, 'domain': 'schematic',
                  'project_path': 'project.cst', 'x_unit': 'GHz', 'y_unit': '1',
                  'x': [110., 140., 170.], 'y': [0.1+0j, 0.2+0.1j, 0.3+0j]}
            for key in ('11', '12', '21', '22')}


def test_four_native_curves_are_kept_asymmetric():
    values = curves()
    values['12']['y'][1] = 0.5 + 0.2j
    report = verify_curves(values, task_name='SP', run_id=3, project_path='project.cst',
                           parameters={'L': '1'}, frequency_unit='GHz', fmin=110, fmax=170, samples=3)
    assert report['max_s12_s21_difference'] == pytest.approx(abs((0.5+0.2j)-(0.2+0.1j)))
    assert report['fresh_execution_verified'] is False


@pytest.mark.parametrize('change', ['missing', 'wrong_run', 'wrong_path', 'grid', 'nonfinite', 'parameters'])
def test_invalid_or_mismatched_curves_are_rejected(change):
    values = copy.deepcopy(curves())
    if change == 'missing': del values['11']
    if change == 'wrong_run': values['11']['run_id'] = 0
    if change == 'wrong_path': values['11']['tree_path'] = 'Tasks\\SP\\S-Parameters\\S2,1'
    if change == 'grid': values['11']['x'][1] = 141
    if change == 'nonfinite': values['11']['y'][0] = complex(float('nan'), 0)
    if change == 'parameters': values['11']['parameters'] = {'L': '2'}
    with pytest.raises(ValueError):
        verify_curves(values, task_name='SP', run_id=3, project_path='project.cst',
                      parameters={'L': '1'}, frequency_unit='GHz', fmin=110, fmax=170, samples=3)
