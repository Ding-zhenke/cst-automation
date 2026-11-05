"""Explicit Python modeling calls on the session-owned application only."""
import inspect
from tpc_service.errors import ServiceError

METHODS = frozenset(('set_units','new_component','new_curve','square','polyline',
    'extrude','add','subtract','create_elliptical_cylinder',
    'create_brick','cylinder','create_cylinder','create_sphere','create_cone','create_torus',
    'configure_sweep','configure_discrete_sweep','add_sweep_parameter_arbitrary_points',
    'change_material','boundary','set_background',
    'create_waveguide_port_free','configure_fem_solver','set_frequency_range',
    'create_field_monitor','add_parameter_sweep_sequence','add_sweep_parameter_samples',
    'set_wcs_basis','activate_global_wcs',
    'triangle','create_triangular_prism','hexagon','create_hexagonal_prism','create_wire',
    'create_polygon','arc','create_arc','ellipse','create_ellipse','create_circle',
    'create_line','create_spline','create_rectangle_curve','create_polygon_3d',
    'extrude_curve','loft_curves','sweep_curve','cover_curve',
    'insert','intersect','boolean_add','boolean_subtract','boolean_insert','boolean_intersect',
    'translate','rotation','rotate','rotate_port','mirror','scale',
    'pick_clear','pick_face','pick_edge','pick_vertex','pick_endpoint',
    'reset_wcs','rotate_wcs','translate_wcs','set_wcs_origin','store_wcs','restore_wcs',
    'create_component','create_material_custom','create_material_tensor','create_material_full_tensor','create_material_gyrotropic',
    'create_waveguide_port','create_discrete_port','create_lumped_element','create_probe',
    'set_boundary','configure_fd_frequency','configure_fd_parallelization','configure_tetrahedral_mesh',
    'delete_solid','delete_curve_item','rotation_face','rotate_face','extrude_face','trace_curve',
    'blend_curve','chamfer_curve','trim_curves','boolean_imprint','blend_edge',
    'set_edge','pick_face_at','pick_edge_at','pick_point_at',
    'align_wcs','wcs_rotate_axis','scale_wcs',
    'rename_solid','rename_component','change_component','change_material_color'))


def _preflight_settings(method, bound):
    """Validate focused configuration payloads before earlier batch mutations."""
    values = dict(bound.arguments)
    values.pop('self', None)
    if method == 'create_material_full_tensor':
        from types import SimpleNamespace
        from cst_solver.material.materials import MaterialMixin
        sink = SimpleNamespace(cst_file=SimpleNamespace(model3d=SimpleNamespace(
            add_to_history=lambda *_: None)))
        MaterialMixin.create_material_full_tensor(sink, **values)
    elif method == 'configure_fd_parallelization':
        from cst_solver.simulation.frequency import normalize_fd_parallelization_settings
        normalize_fd_parallelization_settings(values['settings'])
    elif method == 'configure_fd_frequency':
        from cst_solver.simulation.frequency import normalize_fd_frequency_settings
        normalize_fd_frequency_settings(values['settings'])
    elif method == 'configure_tetrahedral_mesh':
        from cst_solver.mesh.mesh import normalize_tetrahedral_mesh_settings
        normalize_tetrahedral_mesh_settings(values['settings'])
    elif method in ('configure_sweep', 'configure_discrete_sweep'):
        from cst_solver.simulation.sweep import sweep_code, discrete_sweep_code
        builder = sweep_code if method == 'configure_sweep' else discrete_sweep_code
        builder(values['sequence_name'], values['parameters'], values['replace_all'])
    elif method == 'add_sweep_parameter_samples':
        from cst_solver.simulation.sweep import samples_command
        samples_command(values['seq_name'], values['param_name'], values['lower_bound'],
                        values['upper_bound'], values['num_steps'], values['logarithmic'],
                        allow_numeric_strings=True)
    elif method == 'add_sweep_parameter_arbitrary_points':
        from cst_solver.simulation.sweep import points_command
        points_command(values['seq_name'], values['param_name'], values['points'])
    elif method == 'add_parameter_sweep_sequence':
        from cst_solver.simulation.sweep import validate_sequence_name
        validate_sequence_name(values['sequence_name'])
    elif method in ('delete_solid', 'delete_curve_item'):
        from cst_solver.modeling.booleans import _local_name
        for value in values.values():
            _local_name(value)

def validate_calls(calls):
    from cst_solver import setup as CstSetup
    if not isinstance(calls,list) or not 1 <= len(calls) <= 5000:
        raise ServiceError('invalid_session_argument','Bounded modeling calls required')
    for call in calls:
        if (not isinstance(call,dict) or call.get('method') not in METHODS
                or not isinstance(call.get('args',[]),list)
                or not isinstance(call.get('kwargs',{}),dict)
                or set(call)-{'method','args','kwargs'}):
            raise ServiceError('invalid_session_argument','Explicit supported modeling method required')
        try:
            bound = inspect.signature(getattr(CstSetup,call['method'])).bind(
                None,*call.get('args',[]),**call.get('kwargs',{}))
            bound.apply_defaults()
            if 'log_flag' in bound.arguments:
                flag = bound.arguments['log_flag']
                if type(flag) is not int or flag != 1:
                    raise ValueError('Executing model_api calls require log_flag=1')
            _preflight_settings(call['method'], bound)
        except (TypeError,AttributeError,ValueError) as exc:
            raise ServiceError('invalid_session_argument','Invalid modeling method signature',method=call['method']) from exc

def dispatch(app,calls):
    validate_calls(calls)
    receipts = []
    for index, call in enumerate(calls):
        result = getattr(app,call['method'])(*call.get('args',[]),**call.get('kwargs',{}))
        if call['method'] in ('configure_fd_frequency', 'configure_fd_parallelization', 'configure_tetrahedral_mesh'):
            receipts.append({'call_index': index, 'method': call['method'], 'receipt': result})
    return {'python_api_calls':len(calls),'methods':sorted({c['method'] for c in calls}),
            'configuration_receipts': receipts}
