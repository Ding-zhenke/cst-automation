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
任何后续主机操作仍须授权、串行锁及 PID+创建时间核对；本调查不占用 CST。
