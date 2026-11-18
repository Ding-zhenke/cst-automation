# 显式会话与恢复

先通过[后台启动器](../../keysight-ads-simulation/scripts/invoke_hidden.ps1)检查已安装版本的 `-m tpc_service.sessions --help`。在已授权的仓库工作区用所属虚拟环境和后台启动器分配引用。这一步仅登记会话。

```powershell
$sessionRoot = [IO.Path]::GetFullPath((Join-Path (Get-Location) 'work/sessions'))
$conversationRef = [IO.Path]::GetFullPath((Join-Path (Get-Location) ('work/conversations/' + [guid]::NewGuid().ToString() + '.json')))
& .\skills\keysight-ads-simulation\scripts\invoke_hidden.ps1 -Executable .\.venv\Scripts\python.exe -ArgumentList @('-m', 'tpc_service.sessions', '--root', $sessionRoot, '--reference', $conversationRef, 'ensure')
exit $LASTEXITCODE
```

只在首次分配时生成引用，后续使用已记录位置。引用包含私有凭据，不提交或打包。目标仓库若规定固定根目录，服从其约定。

同一 root/reference 下以 status、`job --job-id JOB_ID` 查询，以 resume 恢复。submit 需要稳定 request-id、operation 和按实际 schema 编写的 params-file。先查本机公共 API；几何提交前完成实际参数预览与审阅。

worker 存活接回原队列；丢失则恢复原会话。重连 DE 核对 PID、启动时间与镜像路径；受限环境的空进程列表不证明宿主空闲。恢复失败不改为连接任意窗口。

## 失败与基线审阅

needs_reconcile 阻止未知后续写入。核对原任务、工程摘要、进程/弹窗及保存基线；同一基线和恢复范围已有明确授权时沿用，不因新一轮对话重复询问。确有新未知写入、基线实质变化或现场无法确定时按实际风险重新审阅。只在 `resolve_job_ids` 指定经审阅的任务；保留其他失败、阻塞及原始错误，不自动重放。恢复可能仅到最后保存状态。

close 仅在用户明确要求时提交，使用稳定 request-id。MCP 若已提供对应会话工具可使用同等显式绑定；工具未加载时用同一虚拟环境的 CLI，不修改全局配置。

- 已返回且已保存的电路失败可能让会话恢复 ready。按[已返回保存的电路任务](../../../docs/guides/conversation_sessions.md#已返回保存的电路任务与证据不足)核对项目、run、存盘摘要、先前的不确定状态和弹窗；原 job 仍为 failed，缺少数值证据继续标为未验证。缺少叶日志本身不能判定有 SDK 写入在途。旧保护标记保留。
- 已返回的 Rebuild 带 INFO 时，几何仍可能未验证。已有几何保护只在现场实际空闲、摘要匹配后做[有界只读审阅](../../../docs/guides/geometry_validation_review.md)；保存、重开、重建和解除保护均有独立条件。
- ready 状态下有经审阅的外部保存，按[接受已审阅的外部保存](../../../docs/guides/conversation_sessions.md#接受已审阅的外部保存)核对旧/新摘要、原工程空闲标签、完整原生参数、元件及属性和授权。接受新基线使旧 EM/HB 证据失效，参数范围和求解授权仍按当前规格执行。不得制造故障围栏、手改状态或擅自重启不兼容 worker。

## Worker 交接

- 普通升级要求当前 worker 支持 `cooperative-worker-upgrade-v1`、会话空闲且无保护围栏；原生会话还须确认 DE 已退出。按[协作升级的 begin/finish 操作](../../../docs/guides/conversation_sessions.md#已返回保存的电路任务与证据不足)冻结队列，直至新 worker 读回所需能力。旧版不支持时保留现场。
- 若需保留正在使用的 DE，须获明确授权并完整阅读[保留 DE 的交接程序](../../../docs/guides/native_worker_handoff.md)。区分 owned 与 borrowed，核对旧 worker、启动器和实际 worker 的身份、父子关系与 nonce。保留冻结状态、核实原 DE，在接替 worker 的 SDK 线程重查后按 token 释放。失败启动按专用恢复程序确认原进程树全部退出；禁止重建 DE、强停或任意附加。验收范围以该指南记录的工程、SDK 版本及观测量为限。
- 已返回且保存的静态准备完成后，原 worker 确已退出时，使用 `begin_dead_static_worker_recovery`。核对完整的原失败、完成回执、工程与电路快照摘要、DE 空闲和原进程树消失，继续同一 `finish_native_worker_handoff`。保留失败围栏；该分支不重开工程、不求解。开发契约见仓库 `docs/PUBLIC_API.md` 的“已退出 worker 的静态失败围栏恢复”。
