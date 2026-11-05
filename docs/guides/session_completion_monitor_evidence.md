# 主操作失败时的监测锁存与加载代码证据

## 证据缺口

DialogMonitor.failure 保存本任务首个失败，即使后来 snapshot 变为 clear 也不清除。
旧 worker 在正常返回但监测失败时会返回 cst_dialog_blocked；主操作本身先抛异常时，
monitor.failure 虽参与 returned_saved 判断，却没有进入该主错误回执。只看最后一次
runtime_diagnostics=clear 或把离线判定的 monitor_failure 参数设成 None，会丢掉实际前提。

本次只读检查所属会话指定的已保存回执，确认其错误详情含几何回执，但没有监测收尾
字段、加载代码指纹或状态判定证据。这证明旧回执存在证据缺口，不证明该次曾发生弹窗、
瞬态 monitor_error 或加载了某个旧 worker；不能据此修改旧 job 或解除当前围栏。

## 新回执

主错误 code/message 及完整 geometry_outcome/solver outcome 保留，新增
error.details.session_monitor：

- first_failure：本任务观察到的首个监测失败；
- final_snapshot：收尾时最新的监测快照；
- failure_latched：是否仍持有失败证据。

first_failure 与 final_snapshot=clear 可以同时成立。不会以最终 clear 覆盖首个失败，
也不会重新选择最后一次检测来提高成功等级。读取快照本身失败时，明确记录
state=monitor_error/evidence_source=worker_snapshot_error，保守保留围栏；后续快照恢复
clear 也不丢失第一次读失败。该合成诊断不是声称观察到了原生弹窗。

job.completion_evidence 记录实际 prior_status、decision、reason，unknown/launch 与
monitor_failure_seen、known_saved_geometry/known_saved_solve 等判定因素。例如：

| reason | 含义 |
| --- | --- |
| monitor_failure_latched | 首个监测失败阻止返回保存放行 |
| prior_state_not_ready | 原有会话围栏/其他状态没有被本回执解除 |
| unknown_predecessor / launch_intent_unresolved | 前序工作或环境创建仍未知 |
| saved_receipt_not_verified | 当前身份/返回/保存摘要等没有满足完整检查 |
| verified_returned_saved | 回执完整，job 仍 failed/review_required，session 可 ready |
| read_only_review_preserved_state | 只读查询失败没有改变原写入围栏 |

离线判定函数也读取错误中 session_monitor.first_failure，不能漏传参数后把一个已有
锁存失败解释成 ready。多个不利条件可共存；reason 是主决策原因，其余字段及原错误保留。

## worker 实际加载代码身份

job.worker_runtime 包括真实 worker PID、sys.executable、Python 版本、实现契约修订标记，
以及所选 worker 规则函数、监测收尾函数和已加载 operations.execute 的 code-object SHA256。
它用 marshal 编码当前内存中的 __code__，不读取磁盘源码/HEAD 来冒充已加载版本；
模块尚未加载时指纹为 None。每次执行及收尾留记录，不涉及 Git、SDK 或环境重启。

指纹包含 Python 编码版本和本机代码路径/行号等因素，只能按记录的解释器及工作区解释，
不是跨主机通用签名或完整依赖证明。插件版本、磁盘最新 main 与活跃 worker 的已加载代码
不能互相替代。旧 job 没有此字段时保留未知，不回填当前进程的指纹。

## 使用边界

先看原操作错误、session_monitor 首失败及最终快照，再看 completion_evidence 和
worker_runtime；不要只复制 state 为 ready 并在 monitor_failure=None 下推断原决策。
若有真实窗口，继续读取其标题/正文/按钮/PID/创建身份；若为监测器错误或未知作用域，
保留其具体原因，不直接把它说成 CST 故障或装饰窗口误报。

本次只补诊断，不放松监测规则，不自动重试/重放写入，不清旧围栏，不将几何或求解
未验证提升为通过。部署源码和插件不热刷新现有 worker；当前 DE/现场审阅由所属会话负责。
