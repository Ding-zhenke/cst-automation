# CST 2026 空间网格诊断能力核查

2026-11-02：仅阅读本机官方帮助、随附 Python 示例源码和本仓库接口。
未连接 CST、打开工程或结果、运行示例、解析二进制误差文件、安装或部署运行时。
“已文档化”不是当前工程真机验证；“未找到”不是证明没有内部能力。

## 三项结论

| 需求 | 有依据的入口 | 未获得明确保证的部分 |
|---|---|---|
| 自适应空间/单元误差分布 | 官方描述按边/单元估计误差；通用 ResultMap 和 ASCIIExport | 未找到误差估计 map/err 到单元、坐标、数值的读取或导出接口 |
| 低质量四面体的位置和质量值 | 来源会话已核实 Low Quality Elements 树项可原生高亮定位；另有通用几何反馈 | 未找到原生低质量 tetra ID、连接关系、坐标、质量值清单或表格导出 |
| 实体/区域实际网格统计 | Mesh 全局 getter；官方 Abaqus 示例有按实体名称分组导出路线 | getter 无 shape/bbox 统计参数；示例只覆盖满足机械物性要求的材料，不能证明完整电磁网格可导出 |

以下路径均相对本机 CST 安装目录。

## 1. 空间误差估计

`Online Help/mergedProjects/VBA_3D/special_vbamesh/special_vbamesh_meshadaption3d_object.htm`：
`RefThetaFactor(double value)` 描述为边赋误差度量并选择高误差边细化；
`ErrorEstimatorType(enum {"Automatic"} type)` 是配置，不是误差数组 getter。
`Online Help/mergedProjects/3D/special_solvopt/special_solvopt_adaptive_mesh_refinement_frequency_domain.htm`
的 Special refinement settings / Refinement percentage 描述按边或单元误差选取。
这两页没有给出误差数值的导出方法、坐标/单元绑定、结果树路径或二进制格式。

通用候选接口：

- `ResultMap.Load(name sResultFileMapFile)`、`IsValid()`、`GetContentDescription()`、
  `GetItemCount()`、`GetItemFilename(Integer id)`、`GetItemParameters(Integer id)`。
  来源：`Online Help/mergedProjects/VBA_3D/special_vbapostproc/special_vbapostprocresultmap_object.htm`。
  这是 map 元数据查询，不是单元误差数组；列举类型未明确包含 adaptive-error。
- `ASCIIExport.FileName(filename)`、`SetFileType(enum {"ascii", "csv", "hdf5"})`、`Execute`。
  来源：`Online Help/mergedProjects/VBA_3D/common_vbaimpexp/asciiexport_object.htm`。
  支持受支持的 1D、远场、2D/3D 场结果树条目，不声明任意 err 文件可直接导出。

因此未将 `AdaptErrEst.map` / `Estimate (...).err` 与通用接口强行对应，也不新造专用 API。

### GUI 保存/显示与解系数的补查

2026-11-03 再查官方帮助后，仍未找到频域 tetra 自适应“空间误差估计图”的专用 GUI
保存开关、显示菜单、确定结果树路径，或专用 MeshAdaption3D/FDSolver/ResultTree/Field3D API。
不能将“官方文档未找到入口”写成“GUI 一定可显示但 API 缺失”，也不能写成“当前工程没有保存”。
本会话不访问工程，其是否保存、是否能由现代 Mesh View 展示仍为 unknown。

已确认但必须区分的设置：

| GUI/原生设置 | 文档定义 | 不能推导的结论 |
|---|---|---|
| Home > Simulation > Setup Solver > Frequency Domain Solver > Specials：Save field results at samples；`FDSolver.StoreAllResults(bool flag)` | 保存各采样频率的 E/H/D/B 实际场；GUI 帮助给出 `2D/3D Results > Fields` 下对应子目录，general purpose broadband sweep 支持 | 不等于保存自适应误差场；实际场强热点也不等于离散误差热点 |
| 同一 Specials：Equation system solutions for post-processing；`FDSolver.SetKeepSolutionCoefficients(enum {"All","None","Monitors","MonitorsAndMeshAdaptation"} mode)` | All 为每频点、每激励保留解系数；其他模式关联 monitor 或 adaptation 频率。完整选项仅 general purpose/discrete samples sweep + tetra 可用 | 名称含 MeshAdaptation 不证明保留逐轮误差估计数据或能生成误差图 |
| `FDSolver.StoreSolutionCoefficients(bool flag)` | deprecated，推荐使用 SetKeepSolutionCoefficients；True 保存各频点/激励系数 | 不能将此旧开关称为误差图的已证必要条件或充分条件 |

准确官方位置：

- `Online Help/mergedProjects/3D/special_solvopt/special_solvopt_w3d_specials.htm`：
  页面标题 Special Frequency Domain Solver Parameters；上述两项标签及实际场显示路径。
- `Online Help/mergedProjects/VBA_3D/special_vbasolver/special_vbasolver_fdsolver_object.htm`：
  StoreAllResults、StoreSolutionCoefficients、SetKeepSolutionCoefficients 段。

官方说明，已保留解系数时可能在无需再次求解的情况下生成附加普通场监视器/远场等后处理结果；
这不是补生成已算自适应误差图的保证。未找到为误差图必须事前启用某个 monitor 或上述开关的依据，
所以不建议为了当前调查擅自启用、补监视器或重算。

ResultTree 的 `GetResultFromTreeItem(treepath, resultID)`、`GetFileFromTreeItem(treepath)`
是已有受支持结果的通用入口，并不证明内部误差文件被注册为可读场。
`Online Help/mergedProjects/VBA_3D/special_vbapostproc/special_vbapostproc_type_method.htm`
列举 Efield3D_tet/Hfield3D_tet 等实际场类型，未找到专用自适应误差类型；
不能从带 Field3D 的类型名推断存在通用内部误差 reader。
`special_vbapostproc_result_3d_object.htm` 的 `Result3D.Load(name)` 加载受支持三维结果，
默认扩展名 m3d，也没有声明任意 err 二进制格式可直接加载。本调查不试读或解码。

必须保留四个不同对象：

- 空间误差估计：按边/单元的数值误差指标，目前保存/显示/读取途径未确认。
- Low Quality Elements：已由来源会话核实可高亮的几何质量诊断，不是误差估计。
- E/H/D/B：物理场解及相关普通监视器结果，不是自动的离散误差指标。
- Delta All S：相邻轮次复数 S 的全局变化，不提供唯一空间位置。

敏感 S 通道、增加局部细化后首轮 Delta S 的升降，均不能唯一定位空间误差。
后续只可在 solver 已结束并获授权后，从实际 modeler 树枚举/原生视图和已保存配置取证，
明确对象名称、类型、pass/频率与所用显示窗口；缺项保留 unknown，不能由文档搜索结果替代工程观察。

### 已有估计产物与单次原生元数据探测的边界

来源会话报告已保存基线快照中存在 AdaptErrEst.map、Estimate (...).err、FieldSetFile.fsf、
3d.slim，并已做文件名/大小/哈希及原样字节清单；未解码私有数据或推断坐标。
最后已知保存历史为 SetKeepSolutionCoefficients=MonitorsAndMeshAdaptation、StoreAllResults=False。
应记录 artifact_present=True、history_value_known=True；native_format_readable、
spatial_error_field_readable、current_setting_verified 仍为 unknown。
这不再适合描述为“没有估计相关文件”，但也不能描述为“已读出空间误差场”。

官方 Result3D 文档进一步确认：

- `Set obj = Result3D("")` 构造空对象，不读文件；非空有效结果文件名则直接加载。
- `obj.Load(name sObjectName)` 加载有效 3D 结果，未给后缀时默认 m3d。
- `GetLength`、`IsScalar`、`IsComplex` 是成功加载后的元数据；GetNx/GetNy/GetNz 对 tetra mesh
  为零，因此零值不能单独证明 tetra 场为空。`InitM3T(...)` 创建零值 tetra 数据，不是估计文件 reader。
- 该文档未声明 err/fsf/slim 为支持输入，也没有将这些产物映射到 error-field 类型。
  不将直接对 err 执行 Result3D.Load 作为已支持的探测方案，也不另造 Field3D 构造器。

以下为单次探测前的边界设计。来源任务现已完成唯一一次探测（结果见下段），
不构成继续试读其他 reader 的授权。候选范围限定在官方 `ResultMap` 的 map 元数据链路，
不直接加载误差数组：

1. 记录当前工程/副本和当前树选择。官方 `ResultMap(sTreePath)` 从实际树路径构造；
   `ResultMap("")` 会加载当前树选择，不是空对象。只有明确接受这一上下文读取时才构造，
   无法确认上下文时停止，不靠猜测树路径绕过。
2. 对该对象使用已文档化的 `Reset`，然后只显式 `Load` 一次指向检查副本的 map 文件。
   这不是对该特定 map 支持性的保证，也不能保证原生读取不会报错或弹窗。
3. 只读 `IsValid()`、`GetContentDescription()`；有效时再读 `GetItemCount()`，
   对正数 count 最多查询第一个条目的 `GetItemFilename(1)`、`GetItemParameters(1)`。
   文档示例索引从 1 开始。保留返回原文、异常、执行阶段和真实弹窗；未知类型仍为 unknown。
4. 不调用 `SelectItem`、Result3D.Load、AddToTree、Save、Execute 或导出；不自动追读条目文件，
   不改扩展名、不重试其他 reader，不 Update/solve/history/save。若构造阶段已经出错，
   不再进行 Load；若显式 Load 出错，不追加第二次文件读取。按来源任务的总尝试预算停止。

确切官方位置：
`Online Help/mergedProjects/VBA_3D/special_vbapostproc/special_vbapostprocresultmap_object.htm`
的 Construction、Reset、Load、IsValid、GetContentDescription、GetItemCount、GetItemFilename、
GetItemParameters 和 Example；Result3D 对应 `special_vbapostproc_result_3d_object.htm`。

即使 map 可读且能枚举到 err，最多证明 map 元数据可访问，不能证明空间坐标、单元拓扑、
误差值/定义/单位、pass/频率归属已可读。只有以后取得受支持的实际场读取及这些关联证据，
才能提升 spatial_error_field_readable。本会话未执行任何探测，也未访问所报快照/清单。

### 来源会话已完成的唯一 ResultMap 元数据探测

来源会话报告：solver 全部结束后，持全机锁，在独立检查副本中，以显式选择的既有
S1,1 结果作为构造上下文；Reset 后只执行一次 Load AdaptErrEst.map。原生返回原文如下
（文件路径只保留相对检查副本的部分）：

| 字段 | 原生返回 |
|---|---|
| IsValid | -1 |
| GetContentDescription | Invalid |
| GetItemCount | 1 |
| FirstFilename | 检查副本\Result\Estimate (#0001).err |
| FirstParameters | Frequency=2.8e+11 |

只可确认 map 元数据能枚举一个所标注频率的条目。IsValid 与内容描述应分别保留原值，
不能因 -1 就把 Invalid 改写为受支持的场类型，也不能因 Invalid 就抹掉已枚举的条目。
这里的频率是条目元数据，不证明已从空间场数据验证了实际频率/轮次。
空间误差值、坐标、拓扑和数值定义的读取仍为 unknown。

来源会话未读 err、未新增 solve/mesh/save，且报告原工程和检查副本的 cst 文件哈希均未改变；
不据此扩展为所有依赖文件或全部会话状态均未改变的证明。本会话未连接或复测，
没有追读其他 reader 的计划或授权。

同轮计算的方程残差门槛通过，但 RF 自适应 Delta S 未通过，分别记录；
不能用前者覆盖后者，也不能以这个 map 条目作为空间误差定位已完成的证据。

## 2. 低质量四面体

来源会话补充的真机只读证据（本会话未连接复测）：`Model3D.get_tree_items()` 实际返回
`Mesh\Information\Element Information\Low Quality Elements`，选择后打开既有 Mesh View，
品红色高亮低质量单元位置。这是低质量单元本身的原生可视化定位，不仅是下面的通用几何
feedback。仍未得到单元 ID、坐标、质量值或表格导出，也不等同自适应误差估计分布。
不能因这个结果树条目可视化成功就声称数值导出 API 已验证。

来源会话进一步核实：`ResultTree.GetResultTypeFromItemName(实际路径)` 返回 unknown，
`GetFileFromTreeItem(实际路径)` 返回空字符串，均未抛异常；这不否定该 modeler 树项可视化存在。
SelectTreeItem 能打开现代 Mesh View 并显示高亮，但其后的
`Plot.RestoreView` / `Plot.ZoomToRegion` / `Plot.ExportImage` 操作或导出的仍是 classic 3D 模型，
没有 Mesh View 的低质量高亮。来源会话已人工检查导出图片并标注不可用，因此不能把
Plot.ExportImage 当作这一树项的有效证据导出 API；现代 Mesh View 自身取证路线仍由来源会话核实。
本会话仅记录其验证结果，未连接/部署或复测。

- `Online Help/mergedProjects/3D/common_overview/common_overview_problems_mesh.htm`：
  低质量 tetra 可能影响自适应、条件数和精度，但没有可读回的质量数值/阈值 API。
- `Online Help/mergedProjects/3D/common_overview/common_overview_graphical_feedback.htm`：
  点击 `Navigation Tree: Mesh > Information` 或 feedback issue 链接，可在 3D 视图定位
  自交、靠近的面、错位、细小特征等；不能等同所有低质量体单元的清单。
- `Online Help/mergedProjects/3D/common_modi/common_modi_meshmode_tet.htm`：
  Mesh View 支持 Cutting Plane，Draw solid cutplane 用于显示体网格；无网格时需要 Update，
  本任务不执行。页面未记载逐单元质量值/质量表导出。

Mesh 的 `GetNumberOfCriticalCells`、`GetNumberOfCriticalAreas`、
`GetCriticalCellFromIndex(long index, long_ref icell)`、
`GetCriticalAreaFromIndex(long index, long_ref iarea, long_ref inormal)`
针对几乎被理想导体填满的 critical cells/areas，不是低质量四面体，不能替代本需求。

## 3. 全局统计与有条件的拓扑导出

`Online Help/mergedProjects/VBA_3D/special_vbamesh/special_vbamesho.htm` 支持：

| Mesh 方法（VBA 文档写法） | 返回值及边界 |
|---|---|
| `GetNumberOfMeshCells` | long；全局总单元数，明确包括 hex/tet |
| `GetNumberOfMeshCellsMetrics` | long；hex subgridding 时为原始 metric mesh 数，不是质量指标 |
| `GetMinimumEdgeLength` / `GetMaximumEdgeLength` | double；当前 mesh 的全局最小/最大边长，无区域/实体参数 |
| `GetSurfaceMeshArea` | double；surface mesh 总面积，其他类型或无网格为零；不是 tetra volume 表面积 |
| `GetNp`、`GetXPos/GetYPos/GetZPos(int meshPointIndex)` | 总节点数/normal mesh node 坐标；未给出 tetra 连接关系或实体、bbox 统计保证 |

局部网格设置值不等于实际生成后的局部单元数或质量分布。
`MeshSettings.ItemMeshSettings(...)` 是上下文变更调用，不能试当只读 getter。
本仓库 mesh wrapper 目前主要配置设置，未提供三项所需的完整只读数据链路。

### 官方随附 Abaqus 示例

`Library/Python/lib/cstapps/apps/generate_abaqus_input_file_from_mesh.py`：

- `ABOUT_WINDOW_TEXT`（19 行起）限制为 tetra；只包括材料具有非零 density、Young's modulus、
  thermal expansion coefficient 的部分。可按 shape name 建集合，选择 surface mesh nodes、
  一阶/二阶单元，shape name 长度也有限制。
- `export_input_file(proj, second_order=True, shell_elements=True, shape_names=True)`（473 行）
  通过 `proj.schematic.execute_vba_code` 执行以下官方示例中的命令：
  `PostProcessing3D.Reset()`；`Set("SecondOrderFEElements", ...)`；
  `Set("ConsiderShellElements", ...)`；`Set("ConsiderSolidGrouping", ...)`；
  `Set("Action", "AbaqusExport")`；`Execute()`。
- 这是随附源码中可见的路线，不是已核实稳定性的独立公共 API 保证。
  完整 app 可能触发 Mesh.Update、切换 solver、读取并清空 messages、向工程 Export 目录写文件；
  不能作为对当前主任务的无副作用查询。本任务未 import 或执行脚本。

若未来在独立授权环境取得合格导出，可评估按 shape sets 或空间区域统计导出的网格，
并计算明确命名的外部几何质量指标；不能称为 CST 原生质量值，也不能把导出子集称为完整
电磁网格。不得为了导出擅自补写机械材料物性。当前工程的覆盖范围和可用性仍未验证。

其他边界：`Online Help/mergedProjects/3D/common_tools/common_tools_exportmeshstl.htm`
记载网格 STL 导出，但没有单元误差/质量字段或 tetra connectivity 的文档保证；
不能将 STL 当作带原生质量和实体归属的通用体网格文件。
`Online Help/mergedProjects/3D/special_overview/special_overview_frequency_domain_solver_overview.htm`
说明 Solver Logfile 含 mesh summary 和 solver statistics，不保证按实体/区域统计。

## 后续验收要求

需要实际误差/质量结果树条目或被支持的导出，且明确 mesh pass/频率、单元 ID/坐标、
质量/误差定义、单位、实体/材料覆盖范围后，才能设计相应结果 API。
本次不以敏感 Sij、全局 Delta S 或单条质量警告唯一定位空间区域，不修改物理模型。

保存/复制后的局部配置缺失但网格缓存仍可读这一边界，及其拟议验收合同见
[缓存身份与配置持久化方案](spice-cache-and-mesh-persistence-proposal.md)。
缓存可读不能替代保存重开后的配置读回，也不能据此归因 CST 内部缺陷。
来源会话还观察到生成后即时 Size=0、重开后原长名正确的阶段差异；不能仅凭即时零值判
永久丢失，也不能归因名称长度。Python 侧 bool 不证明 VBA 赋值式调用合法，详见该方案。
任何后续主机操作仍须授权、串行锁及 PID+创建时间核对；本调查不占用 CST。
