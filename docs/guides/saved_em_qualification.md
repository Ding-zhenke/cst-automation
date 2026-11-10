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

**本版尚不能直接覆盖已有内嵌 Touchstone、临时低频文件拟合和端口重排的工程链。**
仅支持同工程内置 EM 块拟合、同顺序、单文件且不缓存的 Touchstone file 块更新。
已有 `TOUCHSTONE block` 的 SetFile 曾被工程使用，不等于 GetFile/GetFilePath
能读出有效内嵌载荷；必须建立有效数据读回后再扩展。不关闭缓存探路，不重建/替换
原拓扑，不隐式改变端口顺序。顺序不同需要显式双射及矩阵两维同步重排的证据。

仅当这两类接口的原生条件满足时才能在工程调用；不能为赶进度用裸 history 绕过。
