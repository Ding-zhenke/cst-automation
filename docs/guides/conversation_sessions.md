# 多对话 CST 持久会话

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
| set_parameters | project_id、values 参数字典；原生阶段会 rebuild 并读消息 |
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

## 明确关闭

```powershell
.\.venv\Scripts\python.exe -m tpc_service.sessions --root $sessionRoot --reference $conversationRef close --request-id close-conversation-a
```

关闭前已接受的任务按序完成；新任务被拒绝。不强杀求解。close_failed 保留环境与错误，
需现场核对。工作工程和日志保留；已明确关闭的绑定不自动重开，后续新绑定可以导入其
保存工程。CST 崩溃、用户手工关闭或系统重启无法保证进程永存；恢复以最后保存为界。

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
