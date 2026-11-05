# EM 改参后自动刷新 HB 曲线并保留历史

## 目标行为

用户手动修改 EM 参数并重跑 EM，随后运行约定的 HB/父任务；HB 成功后，
已绑定的原生后处理自动生成当前参数对应的完整曲线。其他参数对应的曲线
继续保留，能在 CST 中按参数辨认、选择和比较。首次配置完成后，用户无须
每次执行外部导出脚本、手动重建曲线或再次请求刷新。

此目标也适用于长度以外的 EM 参数。自动后处理从实际存储输入和结果读回
参数，不能依赖上一次脚本配置、仅当前编辑框的值或写死的长度标签。
EM 改参但未更新匹配的链接数据，不能用旧 EM/HB 数据生成貌似新的曲线。

完整 RF 响应须在当前参数的全部约定频点和传播方向完成后生成；逐 HB 点的
回调只能积累已核对的数据，不能把一个 gate 的谱线当作完整频扫。缺方向、
缺频点或上游失败保留具体状态，不能补零、混入旧参数数据或标记完整。

交付必须明确实际点击哪个运行入口。兄弟 Post 的顺序不证明“单独运行 HB”
也会触发它；若需要父任务，应交付包含 HB→Post 的单一运行入口并说明。
用户只在 CST 中手动运行时，也应自动完成后处理，不依赖在线聊天补调用。

## 三个独立环节

| 环节 | 所需行为 | 不能替代它的证据 |
|---|---|---|
| HB 原始结果历史 | 各参数组合的复谱可按正 Schematic Run ID 读回 | 当前曲线存在、一个正 ID |
| 派生曲线自动计算和保存 | HB→Post 正确绑定，回调实际运行，输出与真实参数关联并保留历史 | 只有 `.rtpy`、空 Post、静态 Results |
| 参数选择与比较 | 原生 Navigator 多组合选择，或清楚分组的独立 Results 曲线比较 | 仅有导出的 PNG/CSV |

优先打通同一结果叶的原生参数化历史。暂时不能确认原生写入关联时，采用
下述每参数独立 Results；该退路仍须由同一绑定后处理自动生成和保存。
“曲线能自动刷新”和“不同参数曲线都留下”必须同时满足。

## 原生存储的已知入口与缺口

- Spectral Lines/HB 的 Results Settings → Parametric Storage →
  **Calculate results using parametric storage**：官方说明勾选后所有 1D 结果
  按参数保存，未勾选则仅保留当前结果、覆盖之前运行。当前尚未确认这个
  总开关在 `GetResultOption/SetResultOption` 中的精确、版本可靠的键和值。
  不能直接把 UI 标题当作 API 键，也不能借别的结果项的 `On (Parametric)`
  设置声称已开启 HB 总开关。必要时由所属会话在空闲时使用原生 UI 配置，
  并将 UI 配置与纯 API 自动配置分别报告。
- Template Based Post-Processing 的 Active **On** 只计算；
  **On (Parametric)** 才计算并保存参数化结果。这与 HB 存储开关分别核对。
  `eval_type=all_runs` 不是存储开关；当前注册接口仅接受 `single_run`，
  RPP 的 P/EP10 和请求声明不证明实际 Active 或 eval_type 已读回。
- 读取已有历史可用 `GetResultIDsFromTreeItem`、
  `Project.GetParameterCombination` 和 `GetResultFromTreeItem`，以
  `Schematic:RunID:n` 和实际参数组合绑定数据。正 ID 标识参数状态，可能在
  同状态重算时复用或覆盖；另存执行身份，不能把 ID 当不可变执行编号。
- 原生 `SelectTreeItem` 后，`ResultNavigatorRequest("set selection", "1 2")`
  可选择已有结果进行叠加；编号须来自实际结果。它不创建参数历史或写入关联。
  参数列可能隐藏常量或依赖参数；只有一个正 ID、没有长度列/长度图例，
  均不能单独证明存储开关关闭。
- `write_real_curve` 的 `.sig` + ResultTree 写入和单参数 `Result1D.AddToTree`
  尚无已核实的任意正 Run ID 关联入口；不能称为原生参数化写入。不得猜测
  `SetResultID`、修改未知元数据或调用内部 TBPP framework 参数来伪造绑定。

原生模板输出还需验证实际绑定、Active、任务层级及 framework 接收的
Result1D/complex/M1D 返回或 yield 结果。注册持久化通过不等于模板执行、
参数关联、历史保存或 Navigator 叠加已通过。现有接口见
[原生 HB 与后处理](native_hb_postprocessing.md)及
[异常审计与参数绑定](circuit_update_and_result_identity.md)。

## 每参数独立 Results 的自动退路

原生参数化关联尚未验证时，在已授权工程中继续既定扫描，使用绑定回调为
每个实际参数组合生成独立叶，例如 `Results\ParameterCases\<case-key>\<quantity>`。
不因未知 setter 另起求解、重复提问已批准的退路或等待无关接口。当前扫描
未配置该回调时，应报告自动链缺项；不得在扫描中修改任务或声称已自动化。

1. `case-key` 由实际参数数值及单位、其他相关输入/模型配置身份确定，显示
   名称带可辨认参数标签。不能只用四舍五入的长度文本、当前参数值或 Run ID。
   每参数独立结果叶及信号文件；不得反复覆盖一个固定 Results 叶。
2. 在下一个参数/重算可能覆盖原生结果之前，归档当前工况完整复数数据。
   保存实际参数值、表达式及单位，工程/模型/EM 来源与依赖摘要，任务/树路径、
   正 Schematic ID、job/run token 等执行身份、原生日志和成功/缺项状态。
   保存完整实际频轴及所需 DC、泵浦、混频分量的 Re/Im、单位、端口映射、
   电流方向、源入射量、峰值/RMS/相量约定、归一化及参考阻抗。
3. 完整覆盖核对后自动计算派生曲线，连同完整 x/y、公式及代码版本/摘要保存。
   有限功率同频 b/a 仍按该口径标注，不自动称增量小信号 S 参数。派生频响、
   HB 谱线和 EM 普通频率曲线分开命名，不混用频轴或来源。
4. 只刷新同参数同输入匹配且流程拥有的输出；同参数再次运行前保留原始数据
   和不同执行的内容记录，不删除其他参数历史。使用既有工况归档，不为保留
   曲线复制多份 CST 工程。
5. 所属会话在任务已返回、可安全保存的工况边界保存并读回各叶点数、坐标、
   单位、标签与归档一致性；模板不得在求解中嵌套关闭重开或重入外部宏。
   在最终或合适的空闲检查点保存关闭重开，再核对所有参数叶及复数归档。
   保存读回与重开验证分别记录，不为核验打断正在扫描的 CST。

工况清单明确表示 `representation="static_results_snapshot"`，
`native_parametric_storage_verified=False`、
`native_navigator_overlay_verified=False`；未读回的设置为 unknown/null，
不把“未验证”写成“开关关闭”。自动回调执行、数据完整性、保存读回、
重开验证、solver 状态另按实际证据记录。每参数独立 Results 的可见性不证明
原生 Navigator 多组合模式已打通。

交付保留 `.cst`、所需配套资源及完整外部归档，直到单文件封装已实际验证；
PNG、dB 表格或少量指标不能代替原始复数数据。

## 自动链验收

由拥有工程的会话在空闲、获准运行的阶段完成一个有界的双参数组合试验：

1. 手动更改 EM 参数，重跑匹配 EM，再运行同一约定 HB/父任务；用户不执行
   外部刷新操作，绑定后处理确实生成与实际参数匹配的完整曲线。
2. 改为第二组参数重复操作；第二组自动出现，第一组曲线与归档仍可读回，
   标签、数值与来源分别匹配。重复同参数也只能刷新本流程对应的输出。
3. 原生路线核对同一叶的多组正 ID、参数组合、完整复谱、派生曲线关联及
   Navigator 多选叠加；退路核对两组独立 Results 和完整归档，分别报告能力。
4. 安全保存关闭重开后，两组曲线、关联、数据及选择能力仍然成立。

离线检查只能验证代码契约、技能与打包；上述实机链未完成前，明确报告
“自动改参历史曲线尚未验收”，不能以接口存在或文档补全宣称已打通。

## 已实现的独立 Results 入口

`cst_solver.circuit.hb_history` 提供绑定回调和单次托管运行入口。配置仅在
所属工程空闲时进行。`.rtpy` 在 HB 的同一串行 Parameter Sweep 父任务内、
HB 后面的专用 Post 执行；只运行 HB 子项不保证触发 Post。模板返回的 `0D`
是本轮是否已发布的标志（0 收集中，1 已发布），真实曲线在 `Results\HBHistory`。

```python
from cst_solver.circuit.hb_history import (
    run_hb_history, validate_hb_history_settings, write_hb_history_template,
)

# 只填写已核对的工程值；项目适配器随该工程维护。
settings = validate_hb_history_settings({
    "namespace": workflow_name, "task_name": parent_task,
    "adapter": project_adapter_module, "revision": formula_revision,
    "frequency_parameter": rf_parameter_name, "direction_parameter": direction_parameter_name,
    "frequencies": reviewed_rf_points, "directions": reviewed_direction_values,
    "parameter_units": units_by_stored_parameter,
    "em_parameter_map": em_name_to_schematic_name,
    "spectra": {spectrum_path: {"x_unit": spectral_frequency_unit, "y_unit": spectral_value_unit}},
    "normalization": reviewed_wave_and_port_conventions,
})
source = write_hb_history_template(template_path)  # 新建 .rtpy，不覆盖、不连接 CST

# 只在所属会话中、空闲且获准配置时，按实际任务树绑定一次：
app.circuit.register_python_result_template(
    parent_task, hb_task, post_task, source, result_name="HB History Published",
    template_name="HB History", group="HB Results", result_type="0D",
    eval_type="single_run", settings=settings, create=True,
)

# 用户改参并重跑匹配 EM 后，拥有当前工程的编排调用一次；无独立刷新步骤。
outcome = run_hb_history(app.circuit, parent_task, settings=settings,
                         expected_results=verified_expected_parent_results)
history = outcome["hb_history"]
```

工程适配器是 CST 模板解释器可导入的受信任项目模块。需要实现三个函数：

| 函数 | 输入与返回 |
|---|---|
| `observe(*, eval_params, calling_app, prj, settings)` | 返回 `expected_parameters`（当前真实请求数值）、`result_id`（与当点证据绑定的正 Schematic ID）、`point_verified`、`evidence`（当前 HB 完成、来源、日志或其他真实证据）、`configuration_sha256`、`em_source`（`path`、`sha256`、实际 `parameters`，可带其他来源元数据）。手动原生运行时另给 `execution_id`：在同一轮所有回调一致、每轮重新运行唯一，不能用 Run ID、固定字符串或几何参数代替。托管入口提供执行身份。 |
| `read_parameters(*, prj, calling_app, result_id)` | 返回该已存储 ID 的实际全量参数数值。必须使用经验证的读回实现；禁止以当前参数或回调别名伪造存储值。 |
| `derive(*, points, settings)` | 接收按频点、再按配置方向排列的完整工况；每点有实际 `rf`、`direction`、`parameters`、`result_id`、`spectra`（完整 `x/yre/yim` 和单位）。返回 `{quantity: {"y": [...], "y_label": ..., "y_unit": ..., "title": ..., "values_in_db": ...}}`；后两项可省，量名使用安全 ASCII 标识符。输出横轴使用实际 RF 参数值，每个 RF 点输出一个实数；由工程决定公式、相位及归一化口径。 |

`parameter_units` 覆盖全部存储参数，频率/方向两维之外的参数共同标识工况；
`em_parameter_map` 两侧数值必须先按同一单位解释。`normalization` 应记录端口、方向、
波或电压电流约定及参考阻抗。`configuration_sha256` 和 EM 数据摘要须来自本轮
实际输入，`revision` 在派生公式变化时更新。`point_verified=True` 要有同一正 ID 的
当前轮证据，不能从参数相等、回调顺序或历史曲线存在推断。缺少经核验的本机存储
参数 getter 或当前 HB 点证据时先补适配器，不能在回调里猜 ByRef 或嵌套 VBA。

每次托管运行只处理一组固定 EM/其他工况参数，内部扫约定 RF 和方向。每个回调
先核对同一正 ID、存储参数和匹配的 EM 来源，再将完整复谱原子写入相邻的
`<project>.cst.hb-history/<namespace>/run-…`。缺点收集，重复且内容相同不新增，
冲突或发布中断保留失败和已采数据。同参数重跑保留新的执行子组，不删除旧子组；
按 `Results\HBHistory\<namespace>\<case>\<run>\<quantity>` 选择曲线。

`run_hb_history` 调用已有 `run_checked`；回调结束后才走原有保存路径，不在模板内
保存、不重开。核对 `history.status`、`project_save_reported` 与父任务回执；父任务
返回不证明 Post 执行，`callback_not_observed`/`incomplete` 不表示历史已生成。
手动点击已配置的父任务也由回调生成快照，但需适配器证明该次运行身份，且由 CST
工作流完成项目保存；当前没有为任意 GUI 点击提供通用安全自动保存钩子。
保留项目及 `.cst.hb-history` 配套归档。插件只更新技能和说明，不安装项目适配器、
绑定工程或刷新运行中的 CST。此链已用离线替身测试，当前项目的原生绑定、执行与
保存重开仍需上述双参数试验；同一原生叶的参数化写入和 Navigator 叠加仍未打通。

## 本机官方帮助依据（CST 2026）

以下为 Online Help 下的相对路径；它们说明原生语义，不代表本库已完成实机验收：

- `mergedProjects/DES/analysis/simulation/tasks/spectral_lines_simulation_task_results.htm`
- `mergedProjects/DES/analysis/postprocessing/templatebasedpostprocessing.htm`
- `mergedProjects/VBA_DES/special_vbacommands/simulationtaskobject.htm`
- `mergedProjects/VBA_DES/special_vbacommands/projectobject.htm`
- `userinterface/views/resultnavigator.htm`
- `userinterface/views/parametricresultsoverview.htm`
