# 显式会话与恢复

## 首次绑定

先通过[后台启动器](../../keysight-ads-simulation/scripts/invoke_hidden.ps1)检查已安装版本的 `-m tpc_service.sessions --help`。在已授权的仓库工作区用所属虚拟环境和后台启动器分配引用。这一步仅登记会话。

```powershell
$sessionRoot = [IO.Path]::GetFullPath((Join-Path (Get-Location) 'work/sessions'))
$conversationRef = [IO.Path]::GetFullPath((Join-Path (Get-Location) ('work/conversations/' + [guid]::NewGuid().ToString() + '.json')))
& .\skills\keysight-ads-simulation\scripts\invoke_hidden.ps1 -Executable .\.venv\Scripts\python.exe -ArgumentList @('-m', 'tpc_service.sessions', '--root', $sessionRoot, '--reference', $conversationRef, 'ensure')
exit $LASTEXITCODE
```

只在首次分配时生成引用，后续使用已记录位置。引用包含私有凭据，不提交或打包。目标仓库若规定固定根目录，服从其约定。

## 状态查询与提交

同一 root/reference 下以只读 `status` 查询会话。已知 `job_id` 时用 `job --job-id JOB_ID` 读取该任务。只有原 `request_id` 时，在 `status` 返回的 `jobs` 中按 `request_id` 精确匹配，取该条目的 `job_id` 再查。查无匹配时保留“原任务状态未知”，记录引用和请求 ID。只查状态到此结束。

提交已授权的新操作时使用稳定的 request-id、operation 和按实际 schema 编写的 params-file。先查本机公共 API，几何提交前完成实际参数预览与审阅。MCP 若已提供对应会话工具可使用同等显式绑定，工具未加载时用同一虚拟环境的 CLI。

## 接续原任务

超时、断线或宿主启动失败时保留诊断，按[状态查询](#状态查询与提交)定位原 job，核对进程身份、弹窗、目标工程与已保存基线。需要恢复时在同一引用上调用 `resume`。保留原请求和工程，避免重交、复制工程、强停或重放未知写入。

worker 存活时接回原队列并跟踪原 job。worker 丢失后，接替 worker 检查原 `running` 记录。对应 job 的 checkpoint 必须与原 job 的 `fingerprint` 一致，且登记的工程文件存在、磁盘摘要与 checkpoint 的 `saved_digest` 一致。匹配时原 job 记为 `succeeded`、`recovered_from_checkpoint=true`，结果来自该 checkpoint。缺少或不匹配时原 job 转为 `needs_reconcile`，保留现场供审阅。`resume` 后用 `job --job-id JOB_ID` 核实原任务的实际状态和回执。重连 DE 核对 PID、启动时间与镜像路径；受限环境的空进程列表不证明宿主空闲。恢复失败不改为连接任意窗口。

## 按现场选择处理程序

| 当前现场 | 必读程序 |
|---|---|
| 首次导入已复制或登记但失败 | [初始意图恢复](../../../docs/guides/initial_project_intent_recovery.md)，核验磁盘和空闲状态，保留原工程 ID。 |
| 已返回且保存的电路失败、几何未验证、外部保存、`needs_reconcile` | [失败与基线审阅](#失败与基线审阅)，按现场读对应分支。 |
| 停止 3D 后 DS 或后处理状态未明 | [停止与空闲的范围](../../../docs/guides/solver_stop_scope.md)，确认对应序列空闲后再写入或交接。 |
| 维护升级、保留 DE 的交接、静态准备后的旧 worker 已退出 | [Worker 交接](#worker-交接)，核对队列、身份和现场，执行对应完整协议。 |
| 3D History Error 后工程变化且有已验证原生归档 | [受保护归档恢复](../../../docs/guides/model3d_archive_recovery.md)，保留同一事务、备份和原错误，再做定向现场审阅。 |

## 失败与基线审阅

needs_reconcile 阻止未知后续写入。核对原任务、工程摘要、进程/弹窗及保存基线；同一基线和恢复范围已有明确授权时沿用，不因新一轮对话重复询问。确有新未知写入、基线实质变化或现场无法确定时按实际风险重新审阅。只在 `resolve_job_ids` 指定经审阅的任务；保留其他失败、阻塞及原始错误，不自动重放。恢复可能仅到最后保存状态。

- 已返回且已保存的电路失败可能让会话恢复 ready。按[已返回保存的电路任务](../../../docs/guides/conversation_sessions.md#已返回保存的电路任务与证据不足)核对项目、run、存盘摘要、先前的不确定状态和弹窗；原 job 仍为 failed，缺少数值证据继续标为未验证。缺少叶日志本身不能判定有 SDK 写入在途。旧保护标记保留。
- 已返回的 Rebuild 带 INFO 时，几何仍可能未验证。已有几何保护只在现场实际空闲、摘要匹配后做[有界只读审阅](../../../docs/guides/geometry_validation_review.md)；保存、重开、重建和解除保护均有独立条件。
- ready 状态下有经审阅的外部保存，按[接受已审阅的外部保存](../../../docs/guides/conversation_sessions.md#接受已审阅的外部保存)核对旧/新摘要、原工程空闲标签、完整原生参数、元件及属性和授权。接受新基线使旧 EM/HB 证据失效，参数范围和求解授权仍按当前规格执行。不得制造故障围栏、手改状态或擅自重启不兼容 worker。

## Worker 交接

- 普通升级要求当前 worker 支持 `cooperative-worker-upgrade-v1`、会话空闲且无保护围栏；原生会话还须确认 DE 已退出。按[协作升级的 begin/finish 操作](../../../docs/guides/conversation_sessions.md#已返回保存的电路任务与证据不足)冻结队列，直至新 worker 读回所需能力。旧版不支持时保留现场。
- 若需保留正在使用的 DE，须获明确授权并完整阅读[保留 DE 的交接程序](../../../docs/guides/native_worker_handoff.md)。区分 owned 与 borrowed，核对旧 worker、启动器和实际 worker 的身份、父子关系与 nonce。保留冻结状态、核实原 DE，在接替 worker 的 SDK 线程重查后按 token 释放。失败启动按专用恢复程序确认原进程树全部退出；禁止重建 DE、强停或任意附加。验收范围以该指南记录的工程、SDK 版本及观测量为限。
- 已返回且保存的静态准备完成后，原 worker 确已退出时，使用 `begin_dead_static_worker_recovery`。核对完整的原失败、完成回执、工程与电路快照摘要、DE 空闲和原进程树消失，继续同一 `finish_native_worker_handoff`。保留失败围栏；该分支不重开工程、不求解。开发契约见仓库 `docs/PUBLIC_API.md` 的“已退出 worker 的静态失败围栏恢复”。
