# 求解消息、返回回执与会话可用性

本次改动只修复通用证据归属及状态语义，不重新计算、不重写历史任务、不自动解除已有会话核对状态。

## 消息对象及严重程度

保留 SDK 返回的 JSON 可表达消息对象（含 type/text 及其他字段），不先转为字符串。
只使用明确的原生 INFO/WARNING/ERROR 类型；普通字符串、历史 repr、未知类型和无法序列化的对象保持 unknown。
不会靠“看起来正常”的正文降级错误，也不会执行/解析旧 repr 来自动改判旧任务。

| 完整读取的提交后队列 | API 观察状态影响 |
| --- | --- |
| 空或仅 INFO | 不因消息非空失败，仍需原有结果观察条件 |
| WARNING | unverified，保留原消息，必须审阅 |
| ERROR / unknown | failed，保留原消息 |
| 未读或读取失败 | 消息状态未知，不能作为干净队列 |

messages_clean 表示“完整读取且没有非 INFO”，不是空队列；queue_empty 单独记录。
API succeeded 仍不证明原生 solver 完成、结果属于当前 Run ID、网格收敛或指标通过。
native_solver_status、native_warnings_state、mesh_convergence、validation_passed 保持各自证据边界。
文件变化只能证明结果区有变化，不能替代日志、任务/运行身份、矩阵和数值验收。

## 前后队列的时序边界

`setup.run_checked(read_messages=True)` 在提交前后分别调用消息 reader：

1. 先写 before_messages 审计意图；没有可写 sink 时不读取旧队列，也不提交。
2. 读旧队列并写 before_submit 记录。部分读取失败仍保留已读内容；读取/持久化失败不提交。
3. 调用 solver，记录调用是否正常返回，再读提交后队列，形成最终 outcome。

prior_messages 与 messages 分开保存，分别有 summary/state/error；旧警告/错误仍具有独立审阅标志。
不按消息正文做集合相减，相同警告再次出现仍留在提交后队列。
post_boundary_queue 只表示建立了上述时间边界，不代表消息自带了本次原生 Run ID；
没有前置边界则为 pending_queue_unbounded，历史排队消息可能混在其中。
在消费式 reader 返回与捕获记录写入之间突然崩溃，仍是消息/执行回执未知，不能自动恢复为成功。

直接使用 RunContract 时，read_prior_messages 默认 None；显式启用该前置读取时需要可用的审计 sink。
关闭 setup.read_messages 时，前后 reader 均不调用，不能把空容器当作已读成功。

## 失败 job 不总等于未知执行

session solve 正常返回后显式保存。非 succeeded outcome 的 job 继续为 failed，不提升求解状态；
错误中保留 outcome、工程身份、execution_returned 和保存摘要。

仅在以下条件全部满足时，worker 可保留 session ready，并返回 review_required 的保存回执：
该 job 是 solve、明确正常返回且有 run_token、同一登记工程、保存成功、登记/回执/当前磁盘摘要一致，
此前状态为 ready、没有未知前序、launch intent 或 monitor failure。
ready 仅表明运行副作用已知且保存基线可核对；并不是物理结果通过，也不是自动审阅门槛。
既有排队任务可能继续执行，因此依赖失败求解的 HB/Post 必须由调用方显式停止/跳过，
不能依据 session ready 自动提交依赖任务或忽略 failed job。

缺执行回执、保存异常、摘要改变、工程不匹配、弹窗/监测失败、未知写入仍进入 needs_reconcile。
既有 needs_reconcile 不自动清除。该规则不自动改写此前失败 job；旧现场仍按原会话的明确核对流程恢复。

## 验证范围

离线回归使用合成 INFO/WARNING/ERROR、前后队列、审计失败、保存文件及摘要，
覆盖原始结构保留、无文本去重、前置审计不可用时不消费、已保存失败回执与未知执行隔离。
实际工程的日志、固定 Run ID 数据和物理结论由所属模型会话核对；具体模型、参数和原始数据不写入通用库。
