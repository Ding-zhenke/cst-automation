# 3D 停止与 DS 序列空闲的证据边界

本页是 CST 2026 本机官方帮助核对及所属会话回报的范围说明，不是新增停止 API，
没有在运行工程或新夹具中探测。3D 子任务结束、session ready、整个 DS 序列结束
必须分别判断；停止后的日志末尾、归档完整性和交接条件也分别核验。

## 已文档化接口

| 入口 | 官方含义 | 不能推出的结论 |
|---|---|---|
| Python Model3D.abort_solver(timeout=None) | 中止当前运行或暂停的 solver | 整个 DS sequence / sweep 已退出、范围确认窗口已处理 |
| Python Model3D.is_solver_running(timeout=None) | 查询该 solver 是否正在运行 | False 不证明 DS、后处理、停止确认均空闲；没有整个工程 idle 保证 |
| VBA DES SimulationTask.GetNameOfCurrentTask | 仿真过程中返回当前运行的任务名 | 文档未定义空闲、停止确认及外部轮询语义；空值/异常/超时不证明 sequence idle |
| VBA DES GetActivePostprocessingTask | 返回正在运行的 Post-Processing 任务树路径或空串 | 空串只涉及 Post，不排除其他 DS 任务或 sequence 控制器 |
| VBA DES GetTemplateAborted | 用户是否中止模板后处理评估 | 不是整个 DS 仿真停止或空闲状态 |

Python Schematic 的本机接口页列出 execute_vba_code，没有对应的已文档化
abort_solver/is_solver_running。核对 VBA DES Project、SimulationTask、ParameterSweep
帮助后，尚未找到可据此实现可靠全序列 idle/abort 的完整契约；这不证明产品不存在
其他接口。以上 VBA 查询尚未做外部并发轮询验收，不注册为可靠空闲门槛，不用裸宏
绕过被阻塞的所属 worker。SimulationTask.Update / UpdateResults / ParameterSweep.Start
会启动执行，不能用作状态探测。

本机官方来源（相对 CST 安装根目录）：

- Online Help/Python/source/cst.interface.html：Model3D 与 Schematic。
- Online Help/mergedProjects/VBA_DES/special_vbacommands/simulationtaskobject.htm：Queries / GetNameOfCurrentTask；Update 执行当前任务及子任务。
- Online Help/mergedProjects/VBA_DES/special_vbacommands/projectobject.htm：GetActivePostprocessingTask / GetTemplateAborted。
- Online Help/mergedProjects/VBA_DES/special_vbacommands/parametersweepobject.htm：Start 为执行入口。
- Online Help/mergedProjects/DES/analysis/simulation/tasks/simulationtasksequence.htm：Abort if subtask fails 控制是否因子任务失败中止整条序列；不是运行状态 getter。

## Abort 范围确认未处理时

另有一个不同的 Qt Yes/No/Cancel 确认：完整正文为
`Do you really want to abort this calculation?`。已授权停止可使用
[精确 UIA 确认接口](cst_dialogs.md#qt-停止确认的显式-yes)；它仅回答原提示，
不负责发出停止或验证作用域。不得用这个 Yes 处理下述多选 Abort 范围窗口。

所属会话报告：3D abort 返回、EM 日志已记中止及后处理完成、3D running=False、
会话 ready 后，同一 DE 仍发现标题 Abort 的范围选择窗口；有跳过当前任务、跳过当前
参数组合、中止整个参数扫描、中止整个仿真序列等选项。此为“3D 证据不足以放行”的
现场反例。尚不能仅凭先后顺序归因于 abort_solver 的具体内部实现或证明所有版本必现。

窗口未处理、停止请求作用域未确认、DS 终态未知时，停止新写入/求解/worker 交接。
由所属会话在已授权停止范围内处理真实窗口；保留标题、正文、选项、实际选择、按钮、
PID 及原调用回执。取消窗口、窗口消失或 3D False 均不单独证明整个序列终止。
不能为了让检查通过把“跳过一个任务”写成“停止整条序列”。

DS 日志被独占不能证明求解仍计算，也不能证明 idle；日志后来可读同样不是 idle getter。
关键日志或历史 Run 矩阵尚不能完整归档时，保留“归档未完成”，不以大部分文件已复制
放行破坏结果的重建/转换。结合明确的序列终态、当前任务/后处理证据、原调用完整返回、
无未处理窗口及完整保存基线审阅；缺少全序列证据时保持 unknown，不生成伪造的 idle=true。

## 现有交接门槛的真实能力

native_handoff.verify_native 核对精确 DE、标签、全参数、保存基线、前后 PID 范围弹窗，
并两次调用 Model3D.is_solver_running。原理图/全序列空闲仍是调用方的真实审阅声明，
不是独立 DS getter。confirm_idle 必须覆盖原生 EM、DS、后处理及停止确认；session ready、
reconcile 完成、旧审阅通过或过去一次交接验收均不能替代当前证据。
新弹窗/新停止不确定性出现后重新审阅；不要沿用旧确认继续 finish 或自动恢复提交。
