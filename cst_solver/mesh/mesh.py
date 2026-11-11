# -*- coding: utf-8 -*-
"""
CST 网格设置 Mixin 模块
=======================
封装 Mesh、MeshAdaption3D 等网格参数设置

@author: PC
"""

from cst_solver.simulation.frequency import (
    _boolean, _integer, _mapping, _number, _numeric_text, _sequence,
    _submit_configuration,
)


def normalize_tetrahedral_mesh_settings(settings):
    """Pure validation of supported CST 2026 tetrahedral mesh settings.

    Help: VBA_3D/special_vbamesh/special_vbamesho.htm,
    special_vbamesh_meshadaption3d_object.htm and
    common_vbasolido/common_vbasolido_solid_object.htm.
    """
    source = _mapping(settings, ('steps_per_wavelength', 'minimum_steps',
                      'material_refinement', 'local_solids', 'adaptation', 'curvature_order',
                      'curvature_policy'), 'tetrahedral settings')
    result = {}
    if 'curvature_policy' in source:
        policy = source['curvature_policy']
        if not isinstance(policy, str) or policy not in ('automatic', 'fixedorder'):
            raise ValueError('curvature_policy must be automatic or fixedorder')
        result['curvature_policy'] = policy
    if 'curvature_order' in source:
        order = _integer(source['curvature_order'], 'curvature_order')
        if order not in (1, 2, 3):
            raise ValueError('curvature_order must be an integer in {1, 2, 3}')
        result['curvature_order'] = order
    for key in ('steps_per_wavelength', 'minimum_steps'):
        if key in source:
            result[key] = _number(source[key], key)
    if 'material_refinement' in source:
        result['material_refinement'] = _boolean(source['material_refinement'], 'material_refinement')
    if 'local_solids' in source:
        result['local_solids'] = []
        for item in _sequence(source['local_solids'], 'local_solids'):
            item = _mapping(item, ('solid', 'max_step'), 'local solid')
            if set(item) != {'solid', 'max_step'}:
                raise ValueError('Each local solid requires solid and max_step')
            name = item['solid']
            if (not isinstance(name, str) or ':' not in name or
                    any(not part.strip() for part in name.split(':')) or
                    any(ord(char) < 32 or ord(char) == 127 or char == '"' for char in name)):
                raise ValueError('solid must be a safe component:name identifier')
            result['local_solids'].append(dict(solid=name, max_step=_number(item['max_step'], 'max_step')))
    if 'adaptation' in source:
        item = _mapping(source['adaptation'], ('enabled', 'min_passes', 'max_passes',
            'max_delta_s', 'delta_s_checks', 'refinement_percentage',
            'singular_edge_refinement', 'snap_to_geometry', 'refinement_type'), 'adaptation')
        adaptation = {}
        if 'refinement_type' in item:
            if not isinstance(item['refinement_type'], str) or item['refinement_type'] != 'automatic':
                raise ValueError('refinement_type must be automatic')
            adaptation['refinement_type'] = 'automatic'
        if 'singular_edge_refinement' in item:
            level = _integer(item['singular_edge_refinement'], 'singular_edge_refinement', minimum=0)
            if level > 3 or item.get('refinement_type') != 'automatic':
                raise ValueError('singular_edge_refinement requires level 0..3 and explicit refinement_type=automatic')
            adaptation['singular_edge_refinement'] = level
        if 'snap_to_geometry' in item:
            adaptation['snap_to_geometry'] = _boolean(item['snap_to_geometry'], 'snap_to_geometry')
        if 'enabled' in item:
            adaptation['enabled'] = _boolean(item['enabled'], 'enabled')
        for key in ('min_passes', 'max_passes', 'delta_s_checks'):
            if key in item:
                adaptation[key] = _integer(item[key], key)
        if ('min_passes' in adaptation and 'max_passes' in adaptation and
                adaptation['min_passes'] > adaptation['max_passes']):
            raise ValueError('min_passes must not exceed max_passes')
        for key, maximum in (('max_delta_s', 1), ('refinement_percentage', 100)):
            if key in item:
                adaptation[key] = _number(item[key], key, maximum=maximum)
        result['adaptation'] = adaptation
    return result


class MeshMixin:
    """
    CST 网格设置 Mixin
    提供网格属性设置和网格自适应配置功能
    """

    def configure_tetrahedral_mesh(self, settings):
        """Configure documented global/local tetrahedral controls without meshing.

        Local max_step uses current geometry units. Omitted settings are retained;
        no Mesh/solver reset, geometry creation, rebuild, save or solve occurs.
        """
        requested = normalize_tetrahedral_mesh_settings(settings)
        commands = []
        if set(requested) & {'curvature_order', 'curvature_policy'}:
            commands.append('MeshSettings.SetMeshType "Tet"')
        if 'curvature_order' in requested:
            commands.append(f'MeshSettings.Set "CurvatureOrder", "{requested["curvature_order"]}"')
        if 'curvature_policy' in requested:
            commands.append(f'MeshSettings.Set "CurvatureOrderPolicy", "{requested["curvature_policy"]}"')
        has_global_controls = bool(set(requested) & {
            'steps_per_wavelength', 'minimum_steps', 'material_refinement'})
        warnings = ([
            'Global controls use legacy Mesh setters; effectiveness on the modern active '
            'HF Tet MeshSettings group is unverified. Inspect native effective settings '
            'before relying on a density change.'
        ] if has_global_controls else [])
        for key, native in (('steps_per_wavelength', 'StepsPerWavelengthTet'),
                            ('minimum_steps', 'MinimumStepNumberTet')):
            if key in requested:
                commands.append(f'Mesh.{native} "{_numeric_text(requested[key])}"')
        if 'material_refinement' in requested:
            commands.append(f'Mesh.MaterialRefinementTet {requested["material_refinement"]}')
        for item in requested.get('local_solids', ()):
            commands.append(f'Solid.SetMeshStepwidthTet "{item["solid"]}", "{_numeric_text(item["max_step"])}"')
        adaptation = requested.get('adaptation', {})
        if 'enabled' in adaptation:
            commands.append(f'FDSolver.MeshAdaptionTet {adaptation["enabled"]}')
        if set(adaptation) - {'enabled'}:
            commands.append('MeshAdaption3D.SetType "HighFrequencyTet"')
        if 'refinement_type' in adaptation:
            commands.append('MeshAdaption3D.RefinementType "Automatic"')
        if 'singular_edge_refinement' in adaptation:
            commands.append(f'MeshAdaption3D.SingularEdgeRefinement "{adaptation["singular_edge_refinement"]}"')
            if adaptation['singular_edge_refinement'] > 0:
                warnings.append('Singular-edge refinement may exceed RefThetaFactor and linear mesh-growth limits; convergence is not verified.')
        if 'snap_to_geometry' in adaptation:
            commands.append(f'MeshAdaption3D.SnapToGeometry {adaptation["snap_to_geometry"]}')
        for key, native in (('min_passes', 'MinPasses'), ('max_passes', 'MaxPasses'),
                            ('max_delta_s', 'MaxDeltaS'), ('delta_s_checks', 'NumberOfDeltaSChecks'),
                            ('refinement_percentage', 'RefThetaFactor')):
            if key in adaptation:
                commands.append(f'MeshAdaption3D.{native} "{_numeric_text(adaptation[key])}"')
        return _submit_configuration(self, requested, commands, 'Configure tetrahedral mesh',
            warnings=warnings, global_controls_backend='legacy_mesh' if has_global_controls else None,
            active_mesh_settings_group=None)

    def set_mesh_properties(self, max_cell=None, min_cell=None,
                            lines_per_wavelength=10, mesh_type='PBA'):
        """
        设置网格基本属性

        :param max_cell: float 可选, 最大网格尺寸
        :param min_cell: float 可选, 最小网格尺寸
        :param lines_per_wavelength: int, 每波长网格线数，默认 10
        :param mesh_type: str, 网格类型 'PBA'/'Tetrahedral'/...
        """
        f1 = f"""With Mesh
     .Reset
     .LinesPerWavelength "{lines_per_wavelength}"
     .MeshType "{mesh_type}"
"""
        if max_cell:
            f1 += f'     .MaxCell "{max_cell}"\n'
        if min_cell:
            f1 += f'     .MinCell "{min_cell}"\n'
        f1 += """End With"""
        self.cst_file.model3d.add_to_history("Mesh Properties", f1)

    def configure_mesh_adaption(self, max_passes=6, max_refinement=1e-6,
                                adaptive_tolerance=0.01):
        """
        配置网格自适应

        :param max_passes: int, 最大网格自适应次数，默认 6
        :param max_refinement: float, 最大细化步长
        :param adaptive_tolerance: float, 自适应容差
        """
        f1 = f"""With MeshAdaption3D
     .Reset
     .MaxPasses "{max_passes}"
     .MaxRefinement "{max_refinement}"
     .AdaptiveTolerance "{adaptive_tolerance}"
End With"""
        self.cst_file.model3d.add_to_history("Mesh Adaption Config", f1)

    # ================================================================
    # 补充: 增强网格设置
    # ================================================================

    def set_mesh_auto(self, lines_per_wavelength=10, lower_mesh_limit=10,
                       mesh_type='PBA', ratio_limit=10,
                       smallest_mesh_step='1e-6'):
        """
        配置自动网格参数（增强版）

        :param lines_per_wavelength: int, 每波长网格线数，默认 10
        :param lower_mesh_limit: int, 最低网格线数，默认 10
        :param mesh_type: str, 网格类型 'PBA'/'Tetrahedral'/'Hexahedral'
        :param ratio_limit: int, 网格比例限制，默认 10
        :param smallest_mesh_step: str, 最小网格步长，默认 '1e-6'
        """
        f1 = f"""With Mesh
     .Reset
     .LinesPerWavelength "{lines_per_wavelength}"
     .LowerMeshLimit "{lower_mesh_limit}"
     .MeshType "{mesh_type}"
     .RatioLimit "{ratio_limit}"
     .SmallestMeshStep "{smallest_mesh_step}"
     .Automesh "True"
End With"""
        self.cst_file.model3d.add_to_history("Mesh Auto Config", f1)

    # ================================================================
    # MeshSettings — 网格设置增强
    # ================================================================

    def set_mesh_settings(self, **kwargs):
        """
        设置网格高级参数（通过 MeshSettings 对象）
        支持的关键字参数:
            - Properties: dict, 网格属性键值对

        示例:
            >>> app.set_mesh_settings(StepsPerWavelength=12,
            ...                       MeshType="Tetrahedral")
        """
        settings_code = ""
        for key, value in kwargs.items():
            settings_code += f'     .{key} "{value}"\n'
        f1 = f"""With MeshSettings
     .Reset
{settings_code}End With"""
        self.cst_file.model3d.add_to_history("MeshSettings Config", f1)

    # ================================================================
    # MeshShapes — 网格形状控制
    # ================================================================

    def set_mesh_shape(self, shape='hexahedral'):
        """
        设置网格形状类型

        :param shape: str, 网格形状
            'hexahedral' - 六面体网格
            'tetrahedral' - 四面体网格
            'surface' - 表面网格
        """
        f1 = f"""With MeshShapes
     .Reset
     .ShapeType "{shape}"
End With"""
        self.cst_file.model3d.add_to_history(f"MeshShape: {shape}", f1)

    def set_mesh_region(self, name, priority=0, xmin=None, xmax=None,
                        ymin=None, ymax=None, zmin=None, zmax=None,
                        mesh_type=None, step=None):
        """
        设置网格加密区域

        :param name: str, 区域名称
        :param priority: int, 优先级，默认 0
        :param xmin/xmax/ymin/ymax/zmin/zmax: float 可选, 区域边界
        :param mesh_type: str 可选, 区域网格类型
        :param step: float 可选, 区域网格步长
        """
        f1 = f"""With MeshShapes
     .Reset
     .Name "{name}"
     .Priority "{priority}"
"""
        bounds = [
            ('Xmin', xmin), ('Xmax', xmax),
            ('Ymin', ymin), ('Ymax', ymax),
            ('Zmin', zmin), ('Zmax', zmax),
        ]
        for attr, val in bounds:
            if val is not None:
                f1 += f'     .{attr} "{val}"\n'
        if mesh_type:
            f1 += f'     .ShapeType "{mesh_type}"\n'
        if step:
            f1 += f'     .Step "{step}"\n'
        f1 += """     .Create
End With"""
        self.cst_file.model3d.add_to_history(f"MeshRegion: {name}", f1)
