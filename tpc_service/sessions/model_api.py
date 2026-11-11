"""Explicit Python modeling calls on the session-owned application only."""
import inspect
from tpc_service.errors import ServiceError

SETTINGS_ONLY_CAPABILITY = 'solver-settings-no-rebuild-v1'
MESH_SETTINGS_CAPABILITY = 'mesh-settings-no-rebuild-v1'
MODEL_BAND_CAPABILITY = 'model-band-no-rebuild-v1'
SETTINGS_ONLY_METHODS = frozenset(('configure_fd_linear_solver', 'configure_fd_frequency',
                                 'configure_fd_parallelization', 'configure_tetrahedral_mesh', 'set_frequency_range'))


def settings_only(calls):
    return bool(calls) and all(call.get('method') in SETTINGS_ONLY_METHODS for call in calls)


def settings_capability(calls):
    if any(call.get('method') == 'set_frequency_range' for call in calls):
        return MODEL_BAND_CAPABILITY
    return (MESH_SETTINGS_CAPABILITY if any(call.get('method') == 'configure_tetrahedral_mesh'
            for call in calls) else SETTINGS_ONLY_CAPABILITY)

METHODS = frozenset(('set_units','new_component','new_curve','square','polyline',
    'extrude','add','subtract','create_elliptical_cylinder',
    'create_brick','cylinder','create_cylinder','create_sphere','create_cone','create_torus',
    'configure_sweep','configure_discrete_sweep','add_sweep_parameter_arbitrary_points',
    'change_material','boundary','set_background',
    'create_waveguide_port_free','configure_fem_solver','set_frequency_range','configure_fd_linear_solver','replace_port_with_waveguide',
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
    elif method == 'replace_port_with_waveguide':
        from cst_automation.port_replacement import normalize
        normalize(**values)
    elif method == 'configure_fd_linear_solver':
        from cst_automation.fd_linear import linear_solver_code
        linear_solver_code(values['settings'])
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
    replacements = []
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
            if call['method'] == 'replace_port_with_waveguide':
                replacements.append(dict(bound.arguments))
        except (TypeError,AttributeError,ValueError) as exc:
            raise ServiceError('invalid_session_argument','Invalid modeling method signature',method=call['method']) from exc
    if replacements:
        ids = [r['id_val'] for r in replacements]
        preserved = {int(pid) for r in replacements for pid in r['preserve_ports']}
        if len(replacements) != len(calls) or len(ids) != len(set(ids)) or preserved & set(ids):
            raise ServiceError('invalid_session_argument', 'Replacement-only batch requires unique targets disjoint from preserved IDs')

def dispatch(app,calls):
    validate_calls(calls)
    receipts = []
    if calls[0]['method'] == 'replace_port_with_waveguide':
        from inspect import signature
        from cst_solver import setup as CstSetup
        from cst_solver.simulation.port_replacement import preflight_batch, PortReplacementError
        replacements = [signature(CstSetup.replace_port_with_waveguide).bind(
            None, *c.get('args', []), **c.get('kwargs', {})).arguments for c in calls]
        try:
            preflight_batch(app, replacements)
        except PortReplacementError as exc:
            raise ServiceError('session_port_replacement_failed', str(exc), receipt=exc.receipt) from exc
    for index, call in enumerate(calls):
        from cst_solver.simulation.port_replacement import PortReplacementError
        try:
            result = getattr(app,call['method'])(*call.get('args',[]),**call.get('kwargs',{}))
        except PortReplacementError as exc:
            raise ServiceError('session_port_replacement_failed', str(exc), call_index=index,
                               receipt=exc.receipt, earlier_receipts=receipts) from exc
        if call['method'] in ('replace_port_with_waveguide', 'configure_fd_linear_solver', 'configure_fd_frequency', 'configure_fd_parallelization', 'configure_tetrahedral_mesh'):
            receipts.append({'call_index': index, 'method': call['method'], 'receipt': result})
    return {'python_api_calls':len(calls),'methods':sorted({c['method'] for c in calls}),
            'configuration_receipts': receipts}


def verify_replacements(app, receipts):
    from cst_solver.simulation.port_replacement import verify_after_rebuild, PortReplacementError
    try:
        verify_after_rebuild(app, receipts)
    except PortReplacementError as exc:
        raise ServiceError('session_port_replacement_failed', str(exc), receipt=exc.receipt) from exc
