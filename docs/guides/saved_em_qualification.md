# 已保存 EM 资格核验与网络交接

当前维护接口均通过所属会话 `SessionManager.submit`、会话 CLI submit 或
MCP `submit_cst_session_operation` 显式提交。接口部署不升级正在运行的 worker；
先等原任务结束，并按已有流程独立确认空闲。维护代码不自动接管工程。

## SDK abort 与已保存结果矛盾

`qualify_saved_em` 只读已保存结果和原生日志，不连接控制器、不保存/重建/求解。
原任务必须保留 `session_solve_unverified` 下唯一 run_solver 的 `Aborted by user`
异常，且无监控失败；普通失败不能使用此入口。先按正常流程完成明确的空闲审阅
与 reconcile；核验不能解除 needs_reconcile。原任务保留失败错误，即使既有
reconcile 将其状态标为 resolved，也不会改写成 succeeded。

参数全部必填：

| 参数 | 含义 |
|---|---|
| project_id / em_job_id | 所属工程及原失败 solve 的身份 |
| expected_digest | 原回执、审阅基线及当前保存工程一致的 SHA-256 |
| run_id | 实际保存的正 3D Run ID，不接受当前别名 0 |
| port_ids | 全矩阵的原生端口编号；逐叶核对完整笛卡尔积 |
| fmin_hz / fmax_hz | 本次 EM 必须覆盖的频段，SI Hz |
| required_frequencies_hz | 必需实际样本，逐点核对，不能仅挑代表点 |
| frequency_atol_hz | 频点比较容差，显式 SI Hz |
| delta_s_limit / consecutive_passes | 网格连续达标要求 |
| max_residual | 各激励、各必需频率的原生线性残差上限 |

需要 `saved-em-qualification-v1` 能力。版本/输入代数须仍是原运行代数：执行前的
workflow_guard.em_generation 加一；未发生后续改参/EM，HB 代数同样核对。
CST 2026 英文 Model.log 必须仅包含一个带时区的原生运行，依次记录网格精度达标、
宽带收敛、后处理完成与指定 Run ID；时间落在原任务窗口内，无本轮 abort/failure。
残差取日志中 Calculation/Frequency → Stimulation port → Accuracy/Iterations
记录，逐端口核对频率覆盖和必需样本，不接受任意小数值曲线充当残差。

读取当前保存工程的全部复数 S 叶和 Run ID 参数组合，检查有限值、频轴一致、完整
端口集合与采样。读取前后核对工程及 Model.log/output.txt/Storage.sdb 摘要不变；
任何读取锁、缺失或变化均拒绝。实际结果读取器不会调用 setup 或 DesignEnvironment。

成功产生单独资格回执，下游明确承认这一来源。之后每次使用资格时重新核对原生日志
和该固定 Run ID 的完整矩阵，检测同参数覆盖；合法电路保存可以增加数据库内容，但
不能改变被认证的 EM 数据。失败资格核验不启动重算，也不改变原任务错误。

这是独立保存结果资格，不是把 SDK 报错解释为成功。它不证明独立 DC、MOR 质量、
HB 收敛、器件性能或安全解除现场保护；那些门槛分别保留。

## 警告结果的外部探索性证据

`qualify_exploratory_em` 专用于正常返回并保存、仅因原生警告而失败的当前 EM。
原任务仍为 failed，必须有 returned_saved、无本轮监测失败、匹配代次及保存摘要；
要求当前所属会话 ready/空闲。必须指定实际正 Run ID、完整物理端口、目标频段、
必需的直接采样、频率容差和残差上限。它逐直接采样核对每个激励、同轮原生日志
终止标志及完整保存复矩阵，`acknowledged_warnings` 必须与原回执所有 WARNING 文本
逐项匹配；保留全部 WARNING 和源文件摘要。该入口需 worker
`exploratory-saved-em-v1`；旧 worker 不能使用，不能绕开所属会话或强行重启。

输出只作为外部 ADS 的探索性来源证据，不修改正式 workflow 的 EM 回执，也不放行
CST HB。它不生成 Touchstone；调用方须独立比较交付文件与固定原生矩阵，记录
端口顺序、参考阻抗、文件摘要与单位，再检查 DC/拟合、混频所需完整频段和模型
适用性。网格收敛、物理性能和硬件有效性均未由此认证。超出所保存频段的混频项
拒绝以外推填补；扫描频点的峰值覆盖不证明 0 Hz/DC 已覆盖。

## MOR/DC 与 HB 文件交接

`fit_em_network` / `update_hb_network` 的精确字段见 [公共协议](../PUBLIC_API.md)。
需要 `em-network-input-v1`。拟合使用当前工程的内置 EM 块和官方
Block.ExtractStateSpaceModel，核对设置 getter 后导出 ABCD 与日志；不改源/负载。
输出已存在则拒绝。原生导出名必须事先依据当前版本确认；本机 getter/导出格式的
真实执行仍待工程验证。不得将导出成功提升为拟合数值合格。

拟合后按导出日志实际定义计算频率/DC 响应、拟合误差和无源性，再提交包含原始
拟合产物及新 Touchstone 摘要的分析报告。`mor_fit_max_abs_error` 必须满足显式
上限；原 workflow.evidence_rules 继续全部检查。该报告仍是可信数值分析输入，
接口不会猜测 ABCD 方程、参考阻抗或独立 DC。文件更新还检查完整 v1 S/RI 矩阵、
DC 端点、频段与参考阻抗，更新后和 HB 前读取真实文件引用与端口顺序。

## 实际低频拟合与已有内嵌块

新增 `prepare_hb_embedded_network`，需要 worker 能力 `embedded-hb-network-v1`。
它只进行拟合与内嵌输入更新，不启动 EM/HB；新组合入口尚待所属工程实机验收。
已有 `fit_em_network/update_hb_network` 的普通文件块限制不变。

通过所属会话 submit 提供以下字段（精确结构见公共协议）：

- 身份：`project_id/em_job_id/run_id`，当前成功 EM 或独立资格认证的正 Run ID。
- 来源：`matrix_path/matrix_sha256`，NPZ 恰含 `S/ports` 及 `frequency_hz` 或 `frequency_GHz` 之一。完整正频率矩阵，维度为频率×端口×端口；不能仅提供低频子集。
- 映射：`physical_port_ids` 与 NPZ ports 完全一致，`native_reference_ohms` 为逐端口原生参考，`reference_ohm` 为归一化共同阻抗。原生阻抗是调用方已审阅输入，本接口不认证独立阻抗 getter。
- 采样：`low_frequencies_hz/frequency_atol_hz`。至少三个互异实际样本；逐端口核对最终网格后的原生 Calculation/Accuracy，而非仅匹配插值输出行。目前要求英文 adaptive mesh / interpolative broadband 日志的明确阶段边界。
- 目标：已有 `block_name`、有效内嵌文件 `expected_payload_sha256`、同 NPZ 目录的全新 `output_path`（`.sNp`）。派生的 `_lf.sNp` 也不能已存在。
- 设置：`settings` 恰含 `accuracy_abs/maximum_poles/enhance_dc/passivate`。
- 门槛：`limits` 恰含 `fit_max_error/dc_solve_residual/dc_max_singular/dc_reciprocity_error/roundtrip_error/native_matrix_error/native_sample_residual`。由工程确定，不把其他模型的数值当默认值。

输入完整复数矩阵与同 Run ID 的实际保存矩阵按真实参考阻抗转换后逐项比对。
临时块使用实际低频行，显式选择 BUILT-IN、Max、固定归一化参考和极点/DC/无源选项。
导出 ABCD 与日志后核对散射状态方程、端口、参考阻抗和维度，独立计算低频重构残差、
`S(0)=D-C solve(A,B)`、线性残差、DC 最大奇异值和互易误差。
仅在所有门槛通过后生成零频行；原正频率矩阵保持不变并进行全文件读回比较。
这是拟合的 DC 近似，不是独立零频 EM 求解；低频重构不是留出集验证。

目标必须是已有 `TOUCHSTONE block`、单文件、顺序引脚 1..N，`GetFile` 指向本工程
`Model/DS/Block` 内实际文件。只调用目标的 SetFile，不删除原块、不重接线；不调用
该类型不支持的 IsCachingFiles。物理端口按矩阵顺序映射到 1..N，不从其他块的
显示引脚推断。不进行隐式矩阵重排。

临时块删除后以及目标保存后，对比适配器可读回的块、接线、外部端口、探针方向、
任务身份、单位和参数，并检查原目标引脚和有效内嵌载荷摘要；不声称检查了适配器
未枚举的所有任务属性或探针绑定。现有 HB 原生源/负载断言仍独立执行。

成功回执包含 `artifacts/metrics/source/after/topology`。将其全部 artifacts 加入
当前 EM 的数值报告后重新 `accept_workflow_evidence`，再提交 HB。准备操作会清除
先前报告，保留 EM generation，增加 HB generation；HB 前重查来源、文件摘要和
原生有效载荷/拓扑。原有工程数值门槛与源/负载断言继续生效。

部分失败保留任务和产物，按原会话机制进入现场核对，不自动清理未知状态、重试或
回滚。安装不会升级正在运行的 worker；不得为升级而中断仿真。当前维护只做离线
验证，真实拟合/内嵌更新必须由所属工程在空闲且授权范围内验收。
