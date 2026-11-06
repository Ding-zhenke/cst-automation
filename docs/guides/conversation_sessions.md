# 多对话 CST 持久会话

工程复用、临时标签关闭和最小交付遵循
[工程生命周期](../../skills/cst-sessions/references/project-lifecycle.md)。
`close_project` 只保存并关闭一个登记标签，正式 DE 保留；临时工程关闭后转入
`retired_projects` 审计记录。建模完成且正式工程及配套数据核验完整后，关闭、退休并
删除本任务的过程工程（包括未标记 temporary 的 model.cst），保留正式交付、未完成任务
及最小审计记录；清理不是关闭整个 DE。扫描配置使用 `configure_sweep`，只读原生检查使用
`inspect(native_readback=true)`，核验报告不进入可重播的几何历史。

每个对话使用独立恢复引用、独立 worker、独立 CST DE 和独立工程目录。首次真实操作
启动 DE，后续复用。回复结束、停止等待、MCP 断线都不关闭 DE。只有明确 close 请求
才在已接受任务完成后保存并释放。源码讨论和预览不用启动。

## 直接使用：不需要修改全局 MCP 配置

在本仓库 PowerShell 使用 `.venv\Scripts\python.exe`。首先为当前对话选择一个新的
UUID 文件名，保存其绝对路径供本对话持续使用；不要每轮换文件，也不要所有对话共用
一个 reference.json。下面的 conversation-a 只是示例，不是通用默认文件名。

```powershell
$sessionRoot = 'E:\Autocode\cst-automation\work\sessions'
$conversationRef = 'E:\Autocode\cst-automation\work\conversations\conversation-a.json'
.\.venv\Scripts\python.exe -m tpc_service.sessions --root $sessionRoot --reference $conversationRef ensure
```

ensure 原子保存恢复引用，不打开 CST。中断 ensure 后使用原文件重新执行；不要另建
绑定。引用含本机会话凭据，不提交、不复制给其他对话。若丢失引用，找回该对话之前
记录的路径；服务不会凭窗口标题或 cwd 猜测目标。

把明确参数保存为 `work\create-project.json`：

新器件默认使用下面的 `create_project` 从空工程开始，复用经审查的建模代码而非旧
`.cst` 模板。`import_project` 用于要求续改/恢复的已有工程或确需保留的工程内容。
创建后各阶段、同拓扑扫参和中断恢复继续使用同一 project_id，不反复新建空工程。

```json
{"project_id": "model-main", "project_type": "MWS"}
```

```powershell
.\.venv\Scripts\python.exe -m tpc_service.sessions --root $sessionRoot --reference $conversationRef submit --request-id create-model-main --operation create_project --params-file E:\Autocode\cst-automation\work\create-project.json
.\.venv\Scripts\python.exe -m tpc_service.sessions --root $sessionRoot --reference $conversationRef status
.\.venv\Scripts\python.exe -m tpc_service.sessions --root $sessionRoot --reference $conversationRef job --job-id <返回的job_id>
```

submit 只表示任务已持久接受；以 job 的 succeeded 和 result 判断完成。查询不提交第二次
工作；提交回执丢失则用原 request-id 和原参数重试。request-id 或 operation-id 相同而
内容不同会被拒绝，不能“换个 request-id 再试”来绕开不确定状态。

## 操作与阶段

| operation | params |
| --- | --- |
| start | `{}`，仅验证/复用空 DE |
| create_project | project_id，project_type=MWS 或 DS |
| import_project | project_id，源 CST 工程的绝对 source_path；只首次复制 |
| inspect | project_id；未知状态返回持久现场信息，不冒充原生读回 |
| set_parameters | project_id、values 参数字典；使用 app.update() 参数刷新并读消息，不追加完整 Rebuild |
| history | project_id、稳定 stage_id、name、完整 vba、preview_digest |
| solve | project_id，可选 note；使用现有 run_checked |
| circuit | project_id、kind=build/solve/study、settings=原 circuit handler 参数 |

history 用于通用 CST 历史块，VBA 是受信任用户代码，并非隔离的脚本执行沙箱。提交前
先按真实参数出几何预览并等用户审阅；preview_digest 为该 UTF-8 VBA 的 SHA256，仅
绑定已审阅输入，不能作为“已获用户审批”的证据。每个依赖阶段使用稳定 stage_id；
重复同阶段返回原任务。可用 depends_on 列出前置 operation_id，只有前置 succeeded
才执行。输入变化时显式建立新的阶段版本并更新下游依赖，不自动清空或重建全模型。

工程保存在 `<sessionRoot>/<session_id>/projects/<project_id>/model.cst` 和同名结果目录。
同名源工程也不会混用；持久模式不开放跨会话就地写入。后续操作明确使用 project_id，
手工切换 CST 活动标签不能替换目标。不要同时用旧临时工具或独立 setup() 操作该工程。

## 中断恢复

```powershell
.\.venv\Scripts\python.exe -m tpc_service.sessions --root $sessionRoot --reference $conversationRef resume
```

- worker 尚存：接回原队列，任务继续；不因等待超时重跑。
- worker 丢失：新 worker 取得独占锁；存活 DE 按 PID、启动时间、可执行路径精确重连。
- DE 确认退出：下一次操作创建新一代 DE，打开原工作工程，不再导入源工程。
- 保存检查点与输入指纹、磁盘摘要完全对应：恢复完成回执，不重放历史。
- 其他未完成写入或 DE 创建回执缺失：needs_reconcile，后续写入被阻止，先核对现场。

恢复失败不能回退到 connect_to_any。若需人工核对，读取 status、具体 job 与
runtime_diagnostics 中实际弹窗的标题、正文、按钮及所属 PID。reconcile 仅供用户明确
核对后使用：CLI `reconcile --review-file ABS.json`，内容包括 review_note、全部
project_digests、confirm_idle=true；未知 DE 创建另需完整 environment_identity 或
confirm_no_environment=true。它只记录人工采纳的保存基线，未知任务标 resolved，
首次创建失败且没有落盘的工程意图可以在核对后用 abandon_projects 显式放弃；此操作
不能删除已保存工程，也不能接管其他会话已占用的环境。
不认证几何/求解、不重放任务。blocked 阶段如需继续，必须在核对后使用新的阶段 ID。

## 已返回保存的电路任务与证据不足

`circuit` 的 `kind=solve / operation=run_task` 分别记录 project、run_token、submitted、
execution_returned 和保存时 saved_digest。叶任务没有写新日志时，求解结论仍可为 unverified；
这和调用是否返回、是否保存是两条独立证据线。同一登记工程/任务/运行身份及保存/磁盘摘要
一致，且原会话 ready、没有未知任务/启动意图/弹窗失败时，失败 job 保留完整原 outcome、
execution_state=returned_saved、review_required=true，session 维持 ready。

这不将 job 提升为 succeeded，也不认证数值、工作点、收敛或新曲线归属。调用方先审阅本轮
证据再决定后续依赖阶段；不能按 session ready 自动跑整个任务树。未返回、未保存、摘要
不一致、其他操作或原有 needs_reconcile 保持围栏；不自动改历史任务、不自动 reconcile。

更新源码不刷新已存活 worker。所属会话确证 SDK 调用已返回、DE 空闲、无 running/queued
任务与未处理弹窗后，才可让原 worker 退出并用本仓库同一 `.venv`、同一 root/reference
执行 resume。保留原 DE/PID/创建身份、工程及恢复引用，不关闭 CST、不复制/重算任务，
不要启动第二个 worker 抢占仍被持有的锁。resume 校验原环境身份并重新连接；它不会因本次
补丁自动解除既有 needs_reconcile。旧任务缺少新增返回回执时，不能用曲线存在或新版单元
测试补写证明；历史围栏的处置属于所属会话独立的有审计恢复，不是逐轮数值审批。

## 明确关闭

```powershell
.\.venv\Scripts\python.exe -m tpc_service.sessions --root $sessionRoot --reference $conversationRef close --request-id close-conversation-a
```

关闭前已接受的任务按序完成；新任务被拒绝。不强杀求解。close_failed 保留环境与错误，
需现场核对。正式工程、未完成工作和最小审计日志保留；已完成用途的过程副本按工程
生命周期清理。已明确关闭的绑定不自动重开，后续新绑定可以导入保留的正式工程。CST 崩溃、用户手工关闭或系统重启无法保证进程永存；恢复以最后保存为界。

## MCP 接入

本仓库启动入口：

```powershell
.\.venv\Scripts\python.exe -m cst_mcp --enable-sessions --session-root E:\Autocode\cst-automation\work\sessions
```

这会显式注册 7 个会话工具，不启动 CST。没有自动修改用户全局配置；未加载这些工具
的对话可直接使用上述 CLI。所有工具显式携带 session_id 和 credential，不设置进程内
“当前会话”。MCP 当前没有可信聊天身份输入时，服务只能验证绑定凭据，不能认证真实
聊天归属；每个对话须保留自己的引用，新对话/分叉默认新建绑定。

## 启动权限与证据

常驻 worker 使用固定解释器和固定目录。沙箱仍生效；若工具返回后进程被宿主回收，
或缺少进程身份/SDK 启动权限，保留失败记录，在批准的执行环境启动同一入口。
不尝试迁移到临时目录，不借其他 DE，不自动走 Explorer 或计划任务。已接受任务的
worker 丢失时使用 resume 恢复；实际执行意图仍以持久队列为准。

`--backend fake` 仅用于离线演示；不构成原生读回或求解证据。2026-10-27 空 DE 实测
覆盖双环境、跨客户端保留、worker 丢失重连原身份与独立关闭；未执行实际几何或求解。
验收边界以 `docs/VALIDATION.md` 为准。


恢复时，如果同一已核实 DE 中的已保存工程标签已关闭，只有匹配的显式基线确认（last_resolution.human_reviewed、每个工程摘要和当前文件摘要全部相同）才允许重新打开该已登记路径。无确认或摘要变化仍拒绝；不接管其他会话、不搜索活动窗口，也不重放建模。


`set_parameters` supports `expressions` alongside `values` to pass UTF-8 parameter descriptions directly to the existing Python `app.para(..., expression=...)` API. Expressions here are descriptions; executable CST formulas remain in values.


## Python API 建模阶段

`model_api` 操作把审核过的 `calls=[{method,args,kwargs}, ...]` 直接分发给持久会话拥有的 `cst_solver.setup`。静态白名单禁止任意代码、动态导入、求解和关闭工程。每阶段携带 stage_id 和规范JSON calls的SHA256 preview_digest；先检查全部方法签名，再按序调用，完成后原生重建、保存及写检查点。底层API内部生成VBA是库实现细节，不再由调用方拼接整个模型的VBA。该路由的离线fake只记录调用，不伪装实机执行。

参数使用 `set_parameters` 的 values 与 expressions；说明优先中文，公式保留原值。旧历史若写死说明，会在重建时覆盖前置说明，所以会话在重建成功后通过现有描述接口恢复本次说明再保存。新工程应从参数API开始，不在历史中写死另一份参数说明。

## 已关闭 working 过程副本退休

使用[显式退休](retire_closed_process_projects.md)处理已关闭、已完成用途但仍在活动登记的本会话过程工程。close_project 的 retire=True 需保存摘要、现场空闲确认与审阅说明；不触碰 DE 或文件，默认关闭行为不变。

## 首次导入与已有标签恢复检查

首次 create/import 的新登记在环境恢复之后写入，不参与旧工程缺标签审阅。已失败并复制目标的旧 import 不自动续接；按[原意图恢复路线](initial_project_intent_recovery.md)真实审阅并记录 resolution 后，沿同一 project_id 检查继续，不重导入或覆盖文件。

## 几何验证失败与原生只读审阅

已返回保存的几何验证失败与未知写入分别记录。对旧几何错误围栏可显式请求[受限只读检查](geometry_validation_review.md)，取得参数/实体证据但不清围栏；纯 INFO 仍不认证外部依赖或几何通过。
