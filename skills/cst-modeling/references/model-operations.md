# 装配、坐标、材料和端口

本页补充容易选错的现有操作。以当前运行库真实签名及当前 CST 版本帮助为准；列出
方法不表示全部方法都已通过实机验收。会话只调用明确白名单，读回应与写模型分开。

## 轮廓与面特征

闭合平面轮廓可用 `create_polygon/create_circle/create_rectangle_curve`，空间折线
用 `create_polygon_3d/create_line/create_spline`。先建立曲线组；多边形闭合、平面
位置和轮廓方向都要由真实参数检查。

`extrude_curve(curve,name,thickness,component,material)` 中 curve 是完整的
`组:轮廓`，拉伸后轮廓会被删除（DeleteProfile=True）。需要再次使用时，应事先规划
副本或重新创建，不能在后续阶段继续引用已消费的轮廓。

`loft_curves` 依赖有序的多个截面；`sweep_curve` 区分路径与截面；`cover_curve`
生成面而不是有限厚度实体。`blend_curve/chamfer_curve/trim_curves` 是轮廓操作，
不与实体倒圆角 `blend_edge` 混淆。复杂参数需核对当前原生对象支持。

`extrude_face/rotate_face` 依赖当前拾取面；`trace_curve` 依赖目标命名曲线，并可能
消费曲线。先核对拾取对象和坐标，不仅看创建后的默认名字。

`create_triangular_prism` 的现有签名没有 component，内部使用 component1；其他
组件需明确 `change_component` 或基于轮廓构建，不能猜测 component 关键字。
三角形的 a 是边长，六边形的 a 是外接圆半径；`create_hexagonal_prism` 支持
component/curve。所有别名仍以真实签名区分。

## 布尔与对象生命周期

`add` 合并；`subtract(target,tool)` 从目标扣除工具；`intersect` 保留公共部分；
`insert` 用于保留材料/独立对象意图的插入。记录操作后的剩余名字、材料和体积。
需要工具复用时在消费前规划；不能仅因树上名字还在便断言拓扑/材料正确。

`boolean_imprint` 与倒圆角有自身前置条件。倒圆角须先拾取真实棱边；半径与扫描
极值检查局部曲率/净间隙。局部改删使用明确名字的 API，保留无关实体与历史。

## 变换、WCS 与拾取

`translate` 的 vector 是位移，`rotation` 的 center 是旋转中心；copy/repetitions/
unite 决定新对象及合并。`rotate` 是几何便利接口；旋转端口优先 `rotate_port`，
其 object='Port' 与 AutoDestination=False 不应被普通实体旋转替代。
镜像端口也要按 Port 对象与实际命名核对，不能假设组件前缀规则与实体相同。
自由波导端口 API 的范围是轴对齐面；斜置结构和端口应分别绕同一中心按同一角度变换，
同时核对 PortOnBound、模式方向和参考面。

`set_wcs_basis(origin,normal,u_vector)` 明确局部基；normal/u_vector 需有效且不共线，
不能依赖轴向缩写推测完整方向。`activate_global_wcs` 恢复全局。其他现有工具包括
align_wcs、set_wcs_origin、rotate_wcs、translate_wcs、store_wcs/restore_wcs。
WCS 操作影响后续创建，不能当成移动既有实体。

`pick_face/pick_edge/pick_vertex/pick_endpoint` 按编号选择；`pick_face_at/pick_edge_at`
按位置选择。几何改变会使编号变化，应读实际状态、清除旧拾取并重新定位。查询
get_face_id_from_point/get_picked_count 和 pick_face_auto 有原生 Pick 接口依赖；
未暴露时不能把 None 当成成功，也不应无界循环候选编号。

## 材料与单位

`create_material_custom(name,epsilon,mu,kappa,...)` 支持普通/损耗材料、可选 tanδ、
颜色及支持的色散系数。kappa 是电导率；颜色只影响显示。该接口材料单位固定为
GHz/mm，色散频率参数应按它转换，不能直接按当前工程单位代入。

库材料使用 new_material/create_material 或显式 load_material_from_file；文件读取
必须在已授权路径内，并核对实际材料来源。不要把未找到材料静默替换为真空。全张量
接口另核对 epsilon/mu 的实虚部、坐标轴、损耗约定和求解器兼容性。

`change_material` 改实体赋值；`change_material_color` 改显示；`change_component`
改分组。扫描电导率前必须检查材料 Kappa 引用扫描参数（例如符号 sigma），只创建
同名工程参数而材料仍为常数不会产生有效材料扫描。

## 边界、背景、端口与监视器

`boundary` 分别设置 xmin/xmax/ymin/ymax/zmin/zmax；核对坐标面名和对称性。
`set_background` 的材料名只对支持的背景映射有效；背景不是任意 Material 指派，
未知介质须按 API 给 epsilon/mu，边界 open 不等于背景材料 Open。

`create_waveguide_port_free` 用显式空间范围，常规 `create_waveguide_port` 依赖面/范围
设置。`create_discrete_port` 依赖端点及电压方向；`create_lumped_element` 表示电路
负载，不是传播模式端口。Floquet/cable、源和场源也有已有 API，但仅在需求匹配、
当前版本支持、会话路由明确时使用；不为补能力列表给普通两端口器件添加无关激励。

已有离散/波导端口改成同编号波导端口，用 `replace_port_with_waveguide(id_val,
settings, expected_type=..., preserve_ports=...)`。必须给全部数值坐标范围、朝向、
模式数及布尔 port_on_bound；此版本不接受符号坐标。保留端口用编号字符串→类型映射。
批次只能含此替换方法，目标编号不重复且不能同时列为保留端口。它先读原生编号、
类型和模式数，查询不可用时在删除前拒绝；替换后及完整重建后再核对。此为拓扑编辑，
先归档需要保留的结果。部分失败不得盲目重放，按回执查现场。
编号/类型/模式数一致不证明截面、边界兼容、模式场、模式阻抗或保留端口电气可用；
这些必须另行验收。模式阻抗与导出矩阵归一化阻抗分开记录。

端口旋转、模式极化、参考面与几何一起检查；monitor2d 在省略范围时可能查询模型
包围盒，create_field_monitor 则按类型和频率建监视器。监视器行与 F 求解器 Single/
Automatic 采样行不同，不凭监视器行判断自适应频点是否已设置。

## 外部几何与设置边界

已有 import_sat/import_dxf/import_step/import_iges/import_stl/import_subproject，
需要实际文件、单位和依赖核对；不经通用 model_api 接受任意路径。优先几何 API
构建可参数化的基础体，外部几何只用于已有真实资源或当前任务需要的表示。

旧 set_mesh_auto/set_mesh_properties 以六面体语义为主；旧 configure_mesh_adaption、
set_mesh_shape/set_mesh_region 存在未受当前官方对象支持的命令，不作为 F 四面体方案。
用专用 configure_tetrahedral_mesh/configure_fd_frequency，先做电尺寸/成本决策。
通用 kwargs 原生命令设置器不是已有类型化 API 的替代品。
