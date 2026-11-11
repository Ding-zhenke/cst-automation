# 托管禁用已有 HB 任务

此入口用于明确要求停止后续 CST HB 调度、保留任务定义的配置工作；不是中止
正在运行的任务，也不是全局求解锁。先按 [停止范围](solver_stop_scope.md) 确认
原调用、EM、DS、后处理及停止确认均已结束。confirm_idle 是所属会话的审阅声明，
库没有独立的 DS idle getter。未知状态不得填 true。

使用原 session/reference/project_id，通过既有 submit_cst_session_operation
或会话 CLI submit 提交 `operation=circuit`，参数如下（名称仅示例）：

```json
{
  "project_id": "registered-project-id",
  "kind": "build",
  "settings": {
    "operation": "disable_tasks",
    "tasks": [
      {"task_name": "ReviewedSweep", "expected_type": "parameter sweep", "expected_enabled": true},
      {"task_name": "ReviewedSweep\\HB", "expected_type": "spectral lines", "expected_enabled": true}
    ],
    "confirm_idle": true,
    "review_note": "填写当前原生空闲、参数及保存基线审阅依据"
  }
}
```

名称包含实际父级，不加结果树的 Tasks 前缀。不猜子任务名，expected_enabled
来自本次读回；原来已经禁用的任务填 false，接口不会再次写入该任务。1..32 个
不重复目标全部通过 DoesExist、GetTypeForTask 和 GetProperty(enabled) 检查后
才开始修改。仅 SetProperty(enabled, False)，逐一重读存在性、类型及状态；
无 Create/Delete/Update/UpdateResults/ParameterSweep.Start/模板求值。

Python facade 为 `app.circuit.disable_tasks(tasks, confirm_idle=True, review_note=...)`，
不自动保存。受保护工程必须走会话路由；会话复用原工程并保存，保留前后读回。
普通临时 RunService 拒绝此操作，不创建 DE；MCP 沿既有会话提交工具显式注册，
没有新增独立电路工具。旧 worker 缺 `disable-native-tasks-v1` 时拒绝请求；安装
插件不更新正在运行的 worker，不自行交接或重新打开主工程。

原有工作流归属、摘要、输入代次和失败保护仍生效；配置使 HB 设置证据失效，
不把旧 EM/HB 数值重新判为合格。失败可能已部分禁用，保留 partial_build、
before/after/attempted、失败审计及保存状态，不自动回滚或重试。

成功的 readback_verified 仅证明本次 enabled 读回一致；solver_verified、
saved_reopen_verified、result_retention_verified 均为 false。接口不请求删除定义
或结果，但未实机核验结果逐值保留。禁用父任务不冒充子任务不能单独启动；若要求
父、子均禁用，必须逐一列出。重新加载旧保存基线可能恢复旧 enabled 状态。

官方依据：CST 2026 本机帮助
`Online Help/mergedProjects/VBA_DES/special_vbacommands/simulationtaskobject.htm`，
All tasks 的 enabled 属性，以及 Name/DoesExist/GetTypeForTask/GetProperty。
本次仅离线验证，不接触主 DE，不执行新实机试验。
