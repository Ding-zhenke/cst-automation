# 首次项目意图与已有工程恢复

## 回归原因及修复

旧 import_project 先复制目标并写入 saved=False 的新登记，再调用 runtime.environment。
新 worker 精确连接原 DE 时，缺失标签检查把新复制文件也算进旧登记，触发
Absent saved project has no matching explicit review；这时当前 import 尚未调用 open/save。

现在先执行原有复制检查，再恢复旧环境，刷新状态，随后登记新意图并做初次 open/create/save。
因此当前新登记不会参加恢复旧标签的 guard；不是给所有 unsaved 项目增加忽略例外。
旧登记缺标签仍须匹配真实 review 和磁盘摘要，其他未知操作、启动意图与已有围栏不变。
新项目在 native open/create/save 之前仍持久登记 saved=False，失败时由既有状态机保持围栏。
adopt_project 不变。源码更新不热刷新正在使用的 worker。

## 原失败 import 不自动续接

错误文本、saved=False、没有成功 checkpoint、复制源/目标摘要相同，不能独立证明未发生
任何 native 打开、写入或后台操作，也不能代替现场空闲证据。旧回执没有足够明确的
pre-open/无写入审计时，本版不增加自动续接、不自动清 needs_reconcile，也不重新提交
原 import。原目标存在及原 project_id/路径 claim 继续保留；不覆盖文件、不手改 session.json。

需要一次真实的目标基线和现场空闲审阅。按所属会话的既有授权和恢复规则执行；不能为了
继续任务伪造 human_reviewed，也不能把库的离线测试当作当前 DE 的现场证据。
本 API 聊天只提供代码/路线，不执行该现场恢复。

## 有审计的继续路线

1. 读取原失败 job、错误及原请求，保留其不可覆盖副本/摘要；核对原 session/project_id、
   源只读工程、已复制目标及配套目录、当前磁盘摘要和文件归属。确认原任务及其他任务不再运行、
   无排队任务或未处理弹窗，完成对不确定副作用的现场核对，并核实原 DE 身份及实际状态。
2. 只由所属会话在实际空闲时加载修复；不建立新绑定或新 DE，不在这里代替其操作。
3. 审阅完整保存基线后，使用现有 reconcile API/CLI 提交 review_note、全部活动登记的
   project_digests、confirm_idle=True 和需解决的 `resolve_job_ids`；包括这个已有目标文件但 saved=False 的登记。
   若有 launch_intent，还须按既有规则明确处理环境身份。缺证据或审阅未完成则停留在围栏。
4. reconcile 记录真实 resolution/last_resolution，原错误仍保留；只把所指定任务
   标 resolved，而不是 succeeded，其他 failed/blocked 不变。先前保留的原始失败副本仍保留。它采纳磁盘基线，不认证
   import 成功、原生保存、依赖、几何或求解，也不自动重放原任务。
5. 使用新的 inspect 请求并沿同一 project_id 检查。Runtime.project/environment 可按这份
   真实审阅恢复同路径标签，再核对模型/电路/文件依赖。inspect 本身不重导入、不保存或求解。
   原 request-id 重提只返回原回执，不能用它启动新 import；也不对同一登记调用 adopt。
6. 确认正确工程和输入后，再按既有授权、预览和阶段要求继续配置/保存/求解。不得为了
   消掉原错误重放模型、覆盖目标或重新导入源工程。

如果新版本在环境恢复时因某个真实旧工程的审阅缺失而失败，复制可能已完成但新登记尚未
写入；原失败 journal 仍保留目标 claim。需独立审阅文件和现场后经现有恢复流程解决该
journal，再明确决定是否用 adopt_project 登记已审阅文件；不能偷删 claim 或盲目重复复制。
缺失、未保存且无磁盘文件的意图才可考虑既有 abandon_projects，不能为满足条件删除现存目标。

## 验证边界

离线替身覆盖首次 import/create、旧工程 guard 不放宽、native open 异常保留意图，以及
通过真正 reconcile API 记录审阅后沿同一 ID 继续 inspect 的流程。没有在当前实机执行
恢复或打开目标，也不能以这些测试替代实际 review/idle。具体旧任务是否可采纳其复制
基线由所属会话依据完整审计判断；这里不承诺无需人工现场核对。
