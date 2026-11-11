# 失败 3D 历史的受管理归档恢复

状态：0.3.61 离线实现，**原生恢复尚未验收**。适用于原 `model_api/history`
已完整返回原生 `add_to_history` 错误、原 session 处于 `needs_reconcile`，且当前
保存文件已经偏离登记基线。超时、断连、未返回任务不能使用此入口。
不删除单条 History，不保存失败内存，不建网格、不重建、不求解。

## 原会话先准备审阅输入

1. 查原 job 的 finished/failed 与完整原生错误，确认原 SDK、EM、DS、后处理全部
   空闲且无待处理窗口。确认只有目标标签打开；已关闭的其他登记和文件保持。
2. 从已核验归档提取完整成功 `.cst` 到独立工作文件，计算 SHA256。只提取该文件，
   不把归档中零散的日志、网格或结果当成完整 companion 目录。
3. 核对当前登记摘要、当前磁盘摘要、成功源摘要，记录完整 DE/worker 创建身份。
   提供成功基线对应的**全部**原生参数值/表达式与完整端口 ID/type/mode 清单。
   这不是端口几何/阻抗或求解验收；后续按工程要求独立核对这些属性。
4. 确认授权覆盖丢弃目标全部未保存修改、保留失败审计及原 worker 正常退出风险。
   旧 worker 必须已有 `cooperative-worker-upgrade-v1`。0.3.55 的 MODE 冻结与退出
   协议已做源码兼容核查；不热更它，不强杀，不要求先绕围栏 reconcile。

## Python / CLI / MCP

在新客户端进程使用已发布源码及同一解释器、原 root/reference：

```python
review = dict(
    project_id=original_project_id,
    failed_job_id=original_failed_job_id,
    environment_identity=original_de_identity,  # full pid/started/image
    worker_identity=original_worker_identity,
    registered_digest=registered_sha256,
    current_digest=current_disk_sha256,
    source_path=extracted_successful_cst_absolute_path,
    source_digest=successful_cst_sha256,
    expected_parameters=reviewed_full_parameter_map,
    expected_ports=reviewed_full_port_inventory,
    forbidden_history_fragment=exact_failed_command,
    review_note=review_and_authorization_basis,
    confirm_idle=True,
    confirm_discard=True,
    accept_worker_exit_risk=True,
)
receipt = manager.begin_model3d_archive_recovery(session_id, credential, **review)
# Advance only this transaction; keep each returned receipt.
receipt = manager.finish_model3d_archive_recovery(session_id, credential)
```

`expected_parameters` 为 `{name: {"value": finite_number, "expression": exact_string}}`；
`expected_ports` 为 `{"1": {"type": "Discrete", "number_of_modes": 1}, ...}`，也支持
Waveguide 类型。身份和映射必须取自该工程证据，不复制示例。精确字段见 PUBLIC_API。

CLI：`begin-model3d-archive-recovery --review-file ABS.json`，之后反复调用
`finish-model3d-archive-recovery`。MCP 对应显式注册的
`begin_cst_model3d_archive_recovery`（review 对象）与
`finish_cst_model3d_archive_recovery`。这些是客户端维护方法，不进入旧 worker 的
普通任务队列；新代码安装不会让旧进程自动加载代码。

## 阶段及保留内容

- `recovery_reviewing`：已冻结提交，尚未退出旧 worker。只读借用精确目标标签，
  两次读取全部参数和端口，检查 EM idle/实际弹窗。完整复制当前 `.cst` 和整个
  companion 到 `<session>/archive-recovery/<token>/before/`，逐文件核对摘要。
- `stop_requested` 且 pending=true：旧 worker 在既有循环正常写 stop_ack 后退出。
  必须同时观察 ack 和原进程消失；不关闭 DE。DE 丢失则冻结，不新建替代环境。
- `recovery_mutation_claimed`：已持久声明不可自动重放的恢复动作。再查原现场及备份，
  原目标 `Project.close()` 不保存关闭；整个旧 companion 改名到同父目录的
  `<stem>.failed-<token>`。成功 `.cst` 校验复制到原路径，原 DE 打开同一路径。
  保留关闭前完整副本与关闭后的整个隔离目录，不删除失败证据。
- 新目录必须由本次原生打开产生。全参数、端口身份、历史中的失败命令缺失及原生
  消息检查全部通过后，登记成功摘要并清空旧 EM/HB 依赖证据。历史 code 支持字符串
  或 list[str]，读取完整内容。缺 ModelHistory.json、未知格式、任何消息/缺依赖
  都冻结；不从失败 companion 补回文件，也不猜测归档完整性。
- pending=false 后进入既有 preserved-DE 握手。继续调用同一 finish，完成启动令牌、
  新 worker 自身读回及最终短时有效的 release 核对；约 0.5 秒轮询，不长时间忙等。
  新 worker 使用新的目标句柄，已关闭参考标签不会重新打开。
- `complete`：回到 **needs_reconcile**，原失败 job、error 和首失败证据继续保留。
  只有原会话审阅恢复结果、其他实际依赖和新 worker 后，才可定向 reconcile 原
  failed_job_id；不把恢复当 EM/HB 通过，也不自动重交失败请求。

原 `.cst` 及源文件摘要、关闭前 manifest、原 job、原项目登记、原生读回及恢复
阶段都保留在回执/审计目录。关闭参考工程的登记及摘要不得变化或缺文件。

## 拒绝与中断

begin 参数错误不会连接 CST 或冻结。冻结后任何异常保留 phase/last_error，先通过
status 读取；不能手改 session.json、改 request ID、普通 resume/reconcile 绕过维护。
`recovery_mutation_claimed` 后的失败或客户端中断**不自动重试**，即使窗口已消失也
不能推定成功，需独立审阅审计和实际现场。此版不提供任意阶段自动回滚或重复关闭。
若仅在新 worker 启动、尚未 admission 时失败，可按既有 native handoff 的显式
recover 接口核对整个失败进程树退出后恢复；不放宽其限制。

尚未现场证明：隔离后原生重开是否自行生成本版本的历史 JSON、完整外部依赖、
原生句柄交接及矩阵保留。缺项会拒绝而不是从旧文件制造证明。
