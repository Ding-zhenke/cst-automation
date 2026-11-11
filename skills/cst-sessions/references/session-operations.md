# 显式会话与恢复

先检查已安装版本的 `python -m tpc_service.sessions --help`。以下 PowerShell 在已授权工作区分配引用，不启动 CST：

```powershell
$sessionRoot = [IO.Path]::GetFullPath((Join-Path (Get-Location) 'work/sessions'))
$conversationRef = [IO.Path]::GetFullPath((Join-Path (Get-Location) ('work/conversations/' + [guid]::NewGuid().ToString() + '.json')))
python -m tpc_service.sessions --root $sessionRoot --reference $conversationRef ensure
```

只在首次分配时生成引用，后续使用已记录位置。引用包含私有凭据，不提交或打包。目标仓库若规定固定根目录，服从其约定。

同一 root/reference 下以 status、`job --job-id JOB_ID` 查询，以 resume 恢复。submit 需要稳定 request-id、operation 和按实际 schema 编写的 params-file。先查本机公共 API；几何提交前完成实际参数预览与审阅。

worker 存活接回原队列；丢失则恢复原会话。重连 DE 核对 PID、启动时间与镜像路径；受限环境的空进程列表不证明宿主空闲。恢复失败不改为连接任意窗口。

needs_reconcile 阻止未知后续写入。核对原任务、工程摘要、进程/弹窗及保存基线；同一基线和恢复范围已有明确授权时沿用，不因新一轮对话重复询问。确有新未知写入、基线实质变化或现场无法确定时按实际风险重新审阅。只在 `resolve_job_ids` 指定经审阅的任务；保留其他失败、阻塞及原始错误，不自动重放。恢复可能仅到最后保存状态。

close 仅在用户明确要求时提交，使用稳定 request-id。MCP 若已提供对应会话工具可使用同等显式绑定；工具未加载时用同一虚拟环境的 CLI，不修改全局配置。
