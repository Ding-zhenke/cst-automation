# CST 2026 API 修复与调用边界（2026-11-02）

本轮仅做本仓库离线实现；未连接、启动或关闭 CST，未修改全局 Python。
没有把具体器件、模型卡、源配置或结果数据纳入通用包。

## 发现与最小修复

| 问题 | 归类 | 本轮处理 |
|---|---|---|
| DiscretePort 的 VoltageAmplitude/CurrentAmplitude | wrapper 缺陷 | 按官方定义改为 Voltage/Current |
| 显式坐标使用 picked=True | wrapper 缺陷 | SetP1/SetP2 改为 False，保持表达式坐标 |
| DiscreteFacePort 同名幅度属性 | 不属于上述缺陷 | 官方对象确实使用 VoltageAmplitude/CurrentAmplitude，保持原实现 |
| Qtitan 阴影继承 disabled owner 关系 | 分类缺陷 | 精确类名、同进程 owner、无标题/正文/按钮、读取无错误才标记 decoration；原始快照保留 |
| 正文与按钮读取 | 现有 API 已有能力 | 复用 Win32/UIA；增加 PID 创建时间、owner PID/创建时间、分类与 error_code |
| 读窗失败或所属会话不明 | 守卫缺陷 | 保留失败，防止 SDK 返回后变成成功；服务输出独立错误码 |
| 原生 History Error 的确认 | 显式接口缺口 | 核对完整正文、PID 创建时间和按钮；仅确认，不宣称操作恢复 |
| 受限桌面、IPC 不可达、进程未知 | 诊断缺口 | 新增 checked session 入口；不以空进程表推断空闲，不自动重试 |
| Model3D 与 schematic VBA 方法不同 | 适配/文档缺口 | 按目标探测 callable，仅执行一次；错误后不试另一方法 |
| CircuitProbe 与 Net 新建语义 | 使用方调用/文档缺口 | 提供官方对象宏生成器；新 net 用空名，保留生成名并核对连接 |
| 计算完成与收敛混用 | 证据报告缺口 | 独立报告每频率、各轮 Delta S，保留 residual 与 warning；缺失为 unknown |

## 现有细网格继续 refinement：优先调查结论

官方界面帮助 `common_general_mesh_adaption_question.htm` 定义三种选择：

- DISABLE：使用当前网格求解，不再自适应。
- CONTINUE：当前网格作为起点，进行新的自适应轮次。
- RESTART：删除当前网格，从 expert system 生成初始网格。

在本机官方 `MeshAdaption3D`、`FDSolver`、Application 与 Python `cst.interface`
帮助中没有找到可显式选择 CONTINUE 的公开方法/签名。此结论是“所查官方接口未找到”，
不是证明 CST 内部绝不存在此能力，也不构成已经验证的 continuation API。

明确不能替代 CONTINUE：

- `FDSolver.ForceRecalculateOldSamples(bool)`：官方说明已有结果时会关闭自适应。
- `FDSolver.AcceleratedRestart(bool)`：复用频点求解信息以加速重算，不是选择继续网格细化。
- `Model3D.resume_solver(timeout: int = None)`：恢复暂停的求解器。
- quiet mode：控制提示框抑制，没有已核实的 CONTINUE 选择语义。

因此本轮不暴露声称可用的 continue/restart/disable 自动策略。需要继续细化时，待当前
求解结束、全机串行锁和 PID+创建时间核对后，在主机环境读取真实提示并明确选择 CONTINUE；
不要以重新 run、启用自适应或 quiet 模式代替选择。后续可串行录制操作并核对 History 是否
产生可复用命令，再决定是否新增 API。

### 2026-11-03 补查：有界 Continue 的公开语义仍不充分

本次仅再次读取本机官方 HTML 和可读 SDK wrapper，未 import 原生 SDK、连接工程或执行求解。

| 要求 | 官方可确认内容 | 仍未确认 |
|---|---|---|
| 从当前细化网格延续 | `common_general_mesh_adaption_question.htm` 的 CONTINUE 使用当前网格作为新 adaptation passes 起点；RESTART 删除当前网格后重新生成 | 未找到可显式选择该 CONTINUE 的公开 Python/VBA 方法/参数 |
| 限制新增细化次数 | `MeshAdaption3D.MaxPasses(int passes)` 限最大 passes；UI 频域自适应帮助说明多适应频率时上限分别适用 | 继续时该数值是新增次数还是含旧轮次的累计次数、旧 pass index 是否计入，文档未定义 |
| 最小轮次 | `MinPasses(int passes)` 是自适应的最小轮次 | 不能替代 Continue 选择，也不能据此推断 continuation 计数重置 |
| 连续收敛检查 | `NumberOfDeltaSChecks(int value)` 是 S 偏差连续满足 MaxDeltaS 的轮次数 | 不是新增计算轮次预算；改变它会改变验收条件，不能自动改成 1 |

准确本机依据（相对 Online Help）：

- `mergedProjects/3D/common_general/common_general_mesh_adaption_question.htm`，CONTINUE/RESTART 段。
- `mergedProjects/VBA_3D/special_vbamesh/special_vbamesh_meshadaption3d_object.htm`，
  MinPasses/MaxPasses/NumberOfDeltaSChecks/RefThetaFactor 段。
- `mergedProjects/3D/special_solvopt/special_solvopt_adaptive_mesh_refinement_frequency_domain.htm`，
  Number of passes / Maximum 段：最大轮次分别适用于各适应频率，不是跨频率合计预算。
- `Python/source/cst.interface.html`，Model3D.resume_solver/run_solver/start_solver：公开签名仅有 timeout；
  resume_solver 是恢复暂停的 solver，不是已完成或达到 MaxPasses 后选择网格 Continue。
- 安装目录 `AMD64/python_cst_libraries/cst/interface/studio.py` 直接从 `_cst_interface` 导入 Model3D；
  可读 wrapper 未实现额外 continuation 选择器。未检查编译模块内部或声称其绝对不存在内部能力。

`FDSolver.Start` 文档化为按当前设置启动求解，无 Continue 选择参数。
`MeshAdaptionTet(True)` 只是启用自适应；AcceleratedRestart、ForceRecalculateOldSamples 和 quiet mode
均不能作为明确 Continue 的证明。RefThetaFactor 的 cells 增量限制是近似值且可能不被保持，
不能拿 MaxPasses 或细化比例保证某个硬 cells 上限。

因此暂不提供声称可执行的 bounded-continue API：不能承诺 MaxPasses=N 等于“再算 N 轮”，
也不能承诺 MaxPasses=旧轮次+N 是正确策略。需要先取得 continuation 选择方式和计数语义的
权威依据，或在独立授权工程做受控串行验证。应保留已批准的 Checks、阈值和资源上限，
不得用默认弹窗选项、自动确认、旧无界脚本或降低 Checks 替代缺失证据。

本仓库未发现来源任务提及的 continue_em.main，不据其名称推断安全边界，也未运行它。
当前正式 pilot 继续由来源任务控制；本调查不授权占用其会话或改变正在运行的设置。

## 调用示例

以下均为通用示例。真实操作前必须持有全机串行锁并确认其他 CST 工作已完成；
桌面可访问不等于全机空闲。当前任务不执行这些示例。

```python
from cst_solver.host import diagnose_host_session, process_identity, open_host_session

report = diagnose_host_session()  # desktop; IPC、进程可见性与机器空闲可为 unknown
# 在可访问主机上，完成锁定和身份复核后：
# identity = process_identity(target_pid)
# app = open_host_session(pid=target_pid,
#                         expected_creation_time=identity['creation_time'])
```

`creation_time` 是 Windows FILETIME 的精确十进制字符串，不是格式化的本地时间。
若无法读取身份则拒绝 attach。`open_host_session` 为 opt-in：原有 `setup` 调用不变，
服务和使用方需显式迁移到该入口才能获得此项 preflight。打开失败只尝试一次，
报告原始异常；IPC 状态无法从异常可靠区分时不声称已定位原因。
受限环境启动失败与主机环境可用的现象，不足以证明 Crash Report 的唯一根因。

```python
from cst_solver.native import vba_capabilities, execute_vba, circuit_probe_code, new_net_code

# app 已由主机环境显式取得。能力探测不执行宏。
# caps = vba_capabilities(app.cst_file)
code = circuit_probe_code('Vdiff', ('B', 'R1', '1'), ('B', 'R2', '2'))
# execute_vba(app.cst_file, code, target='schematic', timeout=30)
net_code = new_net_code([('Block', 'R1', 0), ('Block', 'R2', 1)])
# execute_vba(app.cst_file, net_code, target='schematic', timeout=30)
```

探针使用引脚名称；Net 使用从零开始的端口 index，两者不能混用。宏生成器不构成原生
对象语义探测：其依据是官方帮助，执行器只探测 Python callable 是否存在。
Model3D 优先使用实际报告存在的 `_execute_vba_code`；若只有公开同名执行器则使用它。
私有入口没有稳定公共 API 保证；本轮未在真机重新验证。
Net 宏把生成名保留在 `GeneratedNetName` 并在 Apply 后检查所有端口所属 net；
它不承诺 Python 能从 `execute_vba_code` 返回生成名，后续外部读回需显式实现。

```python
from cst_solver.dialogs import list_dialogs, acknowledge_known_error

# 快照必须来自已确认身份的目标进程；先检查实际正文和按钮。
# snapshot = list_dialogs(pid=target_pid)[0]
# result = acknowledge_known_error(snapshot,
#     expected_creation_time=identity['creation_time'], button='OK')
# result['readback_status'] == 'required'，即便 action == 'clicked'
```

仅识别精确 History Error 标题及 OK/确定。未知标题不点；不完整文本不点；身份改变不点；
Qt 非标准按钮不通过猜测键盘/坐标点击。确认后必须等原调用返回、保留其异常，重新读取目标状态，
才能决定下一步。既有 DialogMonitor.failure 不会因点了按钮而清空。

```python
from cst_solver.convergence import mesh_convergence_report

report = mesh_convergence_report(
    [{'frequency': 5.0, 'pass_number': 2, 'delta_s': 0.03, 'residual': 1e-5}],
    target=0.01, expected_frequencies=[5.0], max_passes=2,
    computation_completed=True, warnings=['maximum passes reached'])
assert report['convergence'] == 'not_converged'
assert report['validation_passed'] is False
```

这是调用方提供的单次运行、单条 adaptation sequence 证据评价器，不是原生结果提取器。
frequency 必须统一单位；required_passes 应来自实际停止判据。缺频率、缺 Delta S、
不连续轮次均不能补成通过。residual 与 warnings 保留供后续审阅，不作为 Delta S 的替代。
此处 validation_passed 只覆盖传入的计算完成和 Delta S 条件，不是设备性能、原生运行身份、
线性残差或其他停止判据的整体验收。现有 RunContract 默认输出 mesh_convergence=unknown，
validation_passed=False，原有 succeeded 仍仅表示其既有运行契约通过。

## 本机官方依据与待验项目

路径相对 CST 安装的 `Online Help/`，不将本机绝对路径写入发行配置：

- `mergedProjects/VBA_3D/special_vbaports/special_vbaports_discrete_port_object.htm`
- `mergedProjects/VBA_3D/special_vbaports/special_vbaports_discrete_face_port_object.htm`
- `mergedProjects/VBA_DES/special_vbacommands/circuitprobeobject.htm`
- `mergedProjects/VBA_DES/special_vbacommands/net_object.htm`
- `mergedProjects/VBA_3D/special_vbamesh/special_vbamesh_meshadaption3d_object.htm`
- `mergedProjects/VBA_3D/special_vbasolver/special_vbasolver_fdsolver_object.htm`
- `mergedProjects/3D/common_general/common_general_mesh_adaption_question.htm`
- `advanced/vbaapplicationobject.htm`、`Python/source/cst.interface.html`

真机待验：点端口创建/端点 readback；阴影窗口与真实错误同时出现；UIA 失败证据；
PID 复用与已知错误确认后的实际状态；受限/主机桌面诊断与 IPC；原生执行器、差分探针和 Net
生成/读取；完整多频率 adaptation 结果提取；CONTINUE 选择及新增轮次确实从当前细网格开始。
在另一会话求解未完成且全机未确认空闲前，以上项目不得执行。

## 后续补充的真实调用缺口（来源会话报告，本轮未复测）

1. `Project.connect(中文绝对路径)` 抛出 UnicodeDecodeError；同一次主机操作使用
   `DesignEnvironment.connect(已核实 PID).get_open_project(同一路径)` 成功。
   这是路径连接入口差异的案例，不证明中文路径普遍不可用；当前库的 attach 绑定活动工程
   与“按路径取得已经打开的工程”也是不同语义。后续需增加显式 get-open 接口的身份/路径读回，
   不能把连接失败自动降级为新开工程或启动新 DE。
2. `Model3D.pause_solver(timeout=30)` 返回，但 `get_solver_run_info` 仍为 RUNNING，
   网格生成阶段仍有 CPU 活动。返回仅表示控制调用结束，不代表暂停已生效；需要结构化
   requested/pending/paused/failed/unknown 状态与原生运行信息、阶段和时限证据。
3. `Model3D.abort_solver(timeout=30)` 弹出 Qt 确认框；监测能读 Yes/No/Cancel，
   body 为空、text_readable=false。来源会话通过截图读到询问是否终止计算的正文才确认 Yes，
   首次报告时停止尚待确认。不能以按钮存在、abort 返回、确认框关闭或点击 Yes 证明已停止。
   本轮仍保持正文不完整则上报，未加入自动点击。后续需在主机串行复现时保存 UIA provider
   控件树与视觉证据，再改进正文获取；现有 UIA 不可读不能补成猜测正文。
   后续来源会话确认：第二次 abort 保持调用连接有效，确认 Yes 后出现 Aborting，随后询问
   是否恢复最后一次成功计算的解。选择 Yes 后，原生消息为 `Aborted by user` 和
   `Could not load port solution for a discrete face port`，最终 state 为 ERROR；
   原控制器随后退出。中止已完成，但恢复失败，不能称为求解成功、完整矩阵或可用的已恢复解。
   这些控制与结果状态应分别记录，保留原始消息，不能用“中止完成”覆盖 ERROR。
4. `MeshSettings.ItemMeshSettings(group_name)` 不是无副作用 getter，而是选择网格设置
   上下文的变更调用。Python 侧曾观察到 bool；这不能推出 VBA 中支持可赋值的返回函数。
   来源会话对其返回值使用 `dir(...)` 时触发结果兼容性提示，
   已选择 Cancel。这一案例归为使用方调用语义错误，不能据此认定 API 缺失；后续能力检查
   应读取对象属性/官方签名，避免通过调用未知方法来“探测”只读能力。Cancel 也不作为
   所有上下文均已恢复的证明，需要显式 readback。
   后续实测 `ok = MeshSettings.ItemMeshSettings(...)` 报 10091，而原 `With` 内的
   `.ItemMeshSettings(...)` 调用形式可配合读回；两种语言/调用形式的证据不能互相替代。
5. 求解后可能出现 solver-generated 特殊实体，例如报告中的 `special air_0:brick`。
   `Solid.GetLooseBoundingBoxOfShape` 对该特殊体返回 `no simple bounding box`，
   不能直接解释为原始几何实体损坏。几何 readback 应独立记录实体来源、特殊体名称、
   bounding-box 查询的支持状态和原始错误；只有明确识别的自动生成特殊体才归类为
   unsupported_special_body，普通实体或来源不明实体仍保留失败/unknown，不一概忽略。

原控制器退出不等于全机空闲，也不授权本会话占用 CST。来源会话将继续调整局部网格开展
主任务；本会话仍仅记录，不连接、启动、关闭或操作 CST。

这些是后续连接/控制契约与 Qt 诊断的验收要求，不是本轮已交付并验证的原生暂停/停止 API。

## 逐轮复数 S 结果的枚举更正（来源会话已真机只读核实）

先前仅依据 `cst.results` 的树列表、run ID 列表和主 S 参数曲线判断“未保存逐轮矩阵”，
这一判断不成立。`get_all_run_ids(False)` 与 True 相同，不足以排除逐轮数据：
**mesh pass 可以是某个结果条目的横轴，而不需要每轮对应单独 run ID。**

来源会话已核实：

- `Model3D.get_tree_items()` 列出了 `cst.results` 的树枚举未列出的自适应 S 参数曲线。
  路径结构为 `1D Results\Adaptive Meshing\f=<frequency>\S-Parameters\S<i>,<j>`。
  尖括号表示路径结构中的实际频率/端口编号；读取时必须使用实际枚举得到的完整路径。
- 这些路径可以直接交给 Python `ResultModule.get_result_item(path, run_id=...)` 读取。
  来源会话是在已有 run ID 下读回全部端口对，不需要构造或猜测逐轮 run ID。
- 曲线 `xlabel='Pass'`，x 是自适应轮次编号，y 是该适应频率下每轮的复数 S 值。
  不能把 x 当频率或将该曲线交给假定“第一列为频率”的普通 S 参数流程。
- 来源会话已全量读回两个适应频率的端口对曲线，使用相邻轮次复数差的绝对值最大值
  复现原生 Delta All S；末轮数据也与主 S 矩阵在数值精度内一致，并核对了参考阻抗。
  本文仅保留通用接口语义，不纳入具体器件的矩阵、数值或主导端口诊断数据。

后续结果 API 应支持联合枚举：保留 Python results 的离线枚举；在调用方显式提供已经
授权的 modeler 会话时，合并 `Model3D.get_tree_items()` 路径，记录路径来源、去重后逐项
核对可读性。不能为补充枚举而隐式连接或新启动 CST。现已通过下面的独立接口实现，
验收证据为离线替身测试；没有在本会话重新连接来源工程验收。

逐轮读取应保留 path、run ID、xlabel、轮次、适应频率、复数值、端口/模式及归一化信息；
不能仅因结果目录名含 S-Parameters 就作为普通频率曲线处理，也不能仅因 Python 树列表
未出现路径就报告结果不存在。既有 `list_s_parameters()` 的普通频率曲线筛选逻辑不应
直接放宽为混入这些 Pass 轴曲线。

这一证据证明来源工程可通过上述路径读取逐轮矩阵，不保证所有 CST 工程均会保存这些曲线，
也不构成本会话的新仿真或本仓库新增提取器的真机验收。Result Cache 仍是官方文档中的
保存路线，但不能再将其视为读取逐轮 S 数据的必要条件。

## 已实现：联合枚举与 Pass 轴读取

三个入口都位于 `cst_solver.Result`，不改变旧的 `get_tree_items()` 返回结构：

```python
# reader 是已创建的 Result，run_id 是本次明确选择的已有 run。
# authorized_modeler 是调用方显式提供的、属于同一工程的 Model3D。
paths = reader.enumerate_result_paths(modeler=authorized_modeler)
report = reader.read_adaptive_s_parameters(
    run_id=run_id, modeler=authorized_modeler, frequency_unit='GHz')

for curve in report['curves']:
    passes = curve['passes']            # 整数轮次，不是频率
    complex_s = curve['s_complex']      # 保留复数，不转换为 dB
    provenance = curve['sources']      # results、modeler 或两者
    frequency = curve['adaptation_frequency']
    normalization = curve['normalization']
```

`frequency_unit='GHz'` 只能在调用方已核实工程单位时填写。不传单位也能读取，单位保留为
None；路径若自带单位则保留原单位，与参数冲突时拒绝读取。频率标记原文始终保留为 raw，
符号表达式不能解析成数值时 value=None，不猜测求值。无 modeler 参数时仅枚举离线 results，
不寻找已有会话。modeler 和结果工程的身份匹配由调用方负责，本接口只调用其树枚举。

已知精确路径时可绕过树枚举，仅使用结果读取器：

```python
curve = reader.read_adaptive_s_parameter(
    exact_tree_path, run_id=run_id, frequency_unit='GHz')
```

此时路径来源记录为 caller；batch 会替换为实际枚举来源。显式非零 run 与原生读回的 run
不一致时拒绝，缺失 run 不回退；显式 0 保留原生“当前结果”别名及可用的 resolved native ID。
路径必须为 Adaptive Meshing 的 S 参数条目，xlabel 必须为 Pass，轮次为严格递增正整数。
缺轮次可保留原始间隔，不插值；空数组、非整数、重复/倒序轮次、长度不符或非有限复数值均失败。

参考阻抗通过 `get_result_item(..., load_impedances=True)` 和 `get_ref_imp_data()` 获取，
保留原生数据、来源及读取异常。未提供或不可读时 normalization.status=unknown，不补 50 Ω。
即便参考阻抗可读，也不推断 power-wave/pseudo-wave 等波定义，wave_definition 仍为 unknown；
没有重归一化。归一化信息未知不会丢弃已读出的 S 曲线，其诊断保留在每条 normalization 中。

枚举返回每个精确路径的来源和逐来源错误。批量读取同时保留枚举报告与逐路径错误；
可读部分仍可返回，但 status=partial、complete=False。无候选项为 not_found，而非成功的空矩阵。
status=ok/complete=True 只表示所有已发现候选项可读且枚举无错；matrix_completeness 始终为
not_evaluated，不保证完整端口/模式/频率覆盖，也不代替原生收敛或求解验收。

普通 `list_s_parameters()` 已限制到主频率结果树，不再从 Adaptive Meshing 提取名字。
通用 `read_1D()` 仍按原始轴返回；Pass 接口使用独立的 passes/s_complex 字段，不复用
频率矩阵和普通 S 参数导出格式。本轮不新增隐式 MCP 工具注册、Delta S 排名或工程修改。

空间误差、低质量四面体及区域统计的本地官方资料核查见
[网格诊断能力边界](mesh-diagnostic-capabilities.md)。该记录区分全局 Mesh getter、
图形 feedback、通用导出和随附 Abaqus 示例的限制，不声称专用诊断导出已可用。

消息未读取却被标记干净的问题及离线测试范围见
[消息观察契约](message-observation-contract-proposal.md)；该项现已在仓库实施并离线验证，
未部署到已安装运行环境。

已存点重算造成诊断频点偏离的边界，以及纯离线计划/频点核对接口见
[指定缺失样点计划](missing-sample-plan.md)。计划不是原生点集保证，abort/频点 mismatch 不判精度失败。

SPICE 内部模型卡缓存、局部组保存重开一致性及低频/RF 验证隔离的新增证据与待实现方案见
[SPICE 缓存与网格持久化](spice-cache-and-mesh-persistence-proposal.md)；本次仅文档，未改变运行时断言。
