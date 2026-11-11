# 失败 3D 历史的受管理归档恢复

状态：0.3.61–0.3.65 的一次同 DE 工程恢复已由所属会话报告验收；范围见
docs/VALIDATION.md，不代表任意版本或工程均已验证。适用于原 `model_api/history`
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
`expected_ports` 为 `{"1": {"type": "Discrete", "number_of_modes": 0}, ...}`，也支持
Waveguide 类型。Discrete 允许原生整数 0，Waveguide 要求整数 >=1；真实 0 不补成 1。
身份和映射必须取自该工程证据，不复制示例。精确字段见 PUBLIC_API。

本机 CST 2026 官方 `Online Help/mergedProjects/VBA_3D/special_vbaports/`
`special_vbaports_port_object.htm` 将 GetType 列为 Waveguide/Discrete；
GetNumberOfModes 的原文仅说返回指定现有端口的模式数，没有明确写“仅波导端口”，
也没有给出 Discrete 的正数下界。允许 Discrete=0 的依据是所属会话完整原生读回，
不能把模式数 0 解释为端口缺失或无效，也不据此修改实际端口属性。

CLI：`begin-model3d-archive-recovery --review-file ABS.json`，之后反复调用
`finish-model3d-archive-recovery`。MCP 对应显式注册的
`begin_cst_model3d_archive_recovery`（review 对象）与
`finish_cst_model3d_archive_recovery`。这些是客户端维护方法，不进入旧 worker 的
普通任务队列；新代码安装不会让旧进程自动加载代码。

## 阶段及保留内容

- `recovery_reviewing`：已冻结提交，尚未退出旧 worker。只读借用精确目标标签，
  两次读取全部参数和端口，检查 EM idle/实际弹窗。完整复制当前 `.cst` 和整个
  companion 到 `<session>/archive-recovery/<token>/before/`，逐文件核对摘要。
  唯一例外为该 companion **根部精确名 `Model.lok`** 的 CST 临时排他锁：不读取或
  复制锁内容，manifest 的 excluded_companion 记录 size/mtime_ns/ctime_ns/inode/mode、
  排除理由及 content_backed_up=false。其余文件（含嵌套 Model.lok、其他锁名）仍逐一
  读取复制，任何 PermissionError 都拒绝；不把排除锁内容称为已备份。
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
0.3.63 允许仍在 recovery_reviewing 的同一事务续接前置失败留下的空 before/：
接口实际核对目录为空、无 before_manifest.json 后继续，不更换 token、不删除目录。
目录非空、已有清单或其他阶段均拒绝此续接。只有全部非排除文件的源/副本摘要及
排除锁元数据前后匹配，才写提交清单；不接受部分快照。成功备份后另行失败仍需
审阅，不通过“空目录续接”覆盖它。
`recovery_mutation_claimed` 后的失败或客户端中断**不自动重试**，即使窗口已消失也
不能推定成功，需独立审阅审计和实际现场。此版不提供任意阶段自动回滚或重复关闭。
若仅在新 worker 启动、尚未 admission 时失败，可按既有 native handoff 的显式
recover 接口核对整个失败进程树退出后恢复；不放宽其限制。

所属会话已报告本次原生重开生成历史 JSON 并完成新句柄交接；完整外部依赖、
矩阵数值保留及其他 CST 版本仍需各自证据。缺项不能从旧文件制造证明。

## 退出后、关闭前的精确 SimProps 差异复核（0.3.64）

仅适用于 phase=recovery_mutation_claimed、最后错误精确为
`Failed companion changed since its verified backup`，且尚无 close_intent、隔离目录、
恢复暂存或重开回执的同一事务。此错误在 0.3.63 及之前的恢复函数中发生于第一次
native 观察及 close 之前，不能推广成任何 mutation_claimed 都可重试。

所属会话先确认原 worker 已 stop_ack 正常退出，原 DE/标签仍在，原 SDK 已返回，
当前 `.cst` 和成功源摘要不变。调用：

```python
receipt = manager.review_model3d_archive_drift(
    session_id, credential,
    expected_token=original_transaction_token,
    review_note=reviewed_preclose_failure_and_temp_drift_basis,
    confirm_preclose=True,
)
# On success the SAME token is stop_requested; continue its original finish.
receipt = manager.finish_model3d_archive_recovery(session_id, credential)
```

CLI 为 `review-model3d-archive-drift --review-file ABS.json`，JSON 就是上例三个关键字
字段；MCP 为 `review_cst_model3d_archive_drift`（review 对象）。不重新 begin、不手改
会话、不删除或覆盖旧 before/ 与 manifest。

接口重新核对完整原备份并读取**全部**当前文件 SHA256，原生参数/端口和单标签状态
也须与退出前相同。仅允许精确 `Temp/DataStore/SimProps/registry.db` 或其同目录下
标准小写 UUID 文件的新增、修改、删除；不开放整个 Temp 树、任意扩展名或子目录。
模型、结果及未知文件只要内容变化就拒绝。mtime 等元数据变化且 SHA 相同不算内容变化。

每次复核生成独立 `preclose-drift/<audit-id>/report.json`，保存完整当前清单、全部
差异、原 manifest 摘要和变动文件副本；旧内容仍在原 before/ 中。复制后再次完整
哈希核对，变化不稳定则拒绝。成功只让原事务回 stop_requested，并不执行关闭或恢复。

下一次 finish 在原生观察后、close 前再做一次完整内容比较和新的临时增量保留。
确认源/目标/进程身份仍一致后，先持久记录 close_intent，再调用 close；有这个标记
之后不可使用本接口。关闭后的原 companion 仍整体隔离保留，不拿临时变化当模型或
数值验收，也不把差异筛查报告当“成功恢复”。

## 已重开工程的精确 INFO 复核（0.3.65）

当已原生关闭并重开，close_intent=True，且最后错误精确为
`Reopened project reported native messages; inspect dependencies without replay`，
不得再次调用恢复、关闭或打开。只读核对现场后使用：

```python
receipt = manager.review_model3d_archive_postopen(
    session_id, credential,
    expected_token=original_transaction_token,
    expected_history_sha256=reviewed_new_native_history_sha256,
    reviewed_messages=complete_reviewed_typed_message_list,
    review_note=reviewed_reopen_and_info_basis,
    confirm_reopened=True,
    confirm_idle=True,
)
# Success prepares handoff; this finish does NOT execute restore again.
receipt = manager.finish_model3d_archive_recovery(session_id, credential)
```

CLI `review-model3d-archive-postopen --review-file ABS.json`，MCP
`review_cst_model3d_archive_postopen`（review 对象）。expected_history_sha256 是
本次重开后原生 Model/3D/ModelHistory.json 的完整 SHA256，不从旧副本取值。

reviewed_messages 必须是按实际顺序完整列出的三个 `{type: "INFO", text: 原文}`：
非 ASCII history 总提示、具体编号 History block 的非 ASCII 提示、schematic window
含任务提示。只支持这组确知语义，block 编号仍须与原拒绝及本次 native 消息精确相同。
任何 ERROR/WARNING、其他 INFO、缺少/变化/不可读消息均拒绝，不把全部 INFO 一律放行。

接口核对原错误、原 worker 已退出、原 DE/唯一打开目标、完整成功源/staged/current
摘要、未改动原备份和隔离目录、完整参数/端口与新历史摘要/失败命令缺失；原生读回
前后重复，原消息继续保存。隔离目录根 Model.lok 的元数据及不读取内容例外保持。
通过后追加 postopen-review 审计并准备同一新 worker 握手，不 close/open/save/mesh，
不混入旧日志、不解除原围栏。原生外部依赖、DS disabled、端口坐标/阻抗等独立检查
仍由所属工程完成；geometry_verified/solver_verified/external_dependencies_verified=False。

随后 finish 完成新句柄交接才回到 needs_reconcile，再按原流程定向 reconcile。
所属会话已报告本次 postopen 复核及完整交接通过；不能用它声称数值验证已经通过。
