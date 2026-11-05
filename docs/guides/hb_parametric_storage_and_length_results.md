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

当前还需具体实现并验证：实际运行入口的自动触发；逐点持久累积及频点/
方向完成判据、重复点和重跑处理；任务返回后的安全自动保存及失败记录。
这些责任必须落在绑定模板/原生任务或随工程交付的明确编排上，不能以
“所属会话以后保存”替代无人值守的自动链。它们与上文的原生设置和写入
关联缺口分别记录；本指南规定目标与退路，不宣称已经补齐运行实现。

## 本机官方帮助依据（CST 2026）

以下为 Online Help 下的相对路径；它们说明原生语义，不代表本库已完成实机验收：

- `mergedProjects/DES/analysis/simulation/tasks/spectral_lines_simulation_task_results.htm`
- `mergedProjects/DES/analysis/postprocessing/templatebasedpostprocessing.htm`
- `mergedProjects/VBA_DES/special_vbacommands/simulationtaskobject.htm`
- `mergedProjects/VBA_DES/special_vbacommands/projectobject.htm`
- `userinterface/views/resultnavigator.htm`
- `userinterface/views/parametricresultsoverview.htm`
