---
name: cst-project-lifecycle
description: Deliver a formal CST project with its required companion data, or close, retire and clean up a finished task's process projects while preserving the owning CST environment.
---

# CST 工程交付与过程工程清理

沿本任务的恢复引用、`session_id`、`project_id` 和所属 DE 核对工作路径、正式路径及用户要求保留的内容。首次原生调用按[宿主与后台启动规则](../README.md#执行环境)进行。需要恢复连接时按[所属会话](../cst-sessions/SKILL.md)接续原任务。

## 核对正式交付

1. 核对正式 `.cst` 的绝对路径与保存摘要，检查 CST 必需的同名配套数据目录，以及工程实际使用的外部文件。确认交付工程能从最终位置解析这些依赖，尤其是指向过程目录的链接。新建或接管正式路径时按[正式工程路径](../../docs/guides/session_formal_project_paths.md)操作。
2. 每个正式建模拓扑保留最终工程、必要配套数据、可复现建模 Python 和所需示意图 PNG。独立参考工程、其他格式或服务器压缩包按当前请求交付。复用现有审计日志和阶段回执，避免为打包重复建模、求解或生成多套备份。
3. 建模结束且上述核验通过后，主动清理已经完成用途的本任务过程工程，包括创建时登记为 `working` 的 `model.cst`。正在编辑的正式工程、必需依赖、用户要求保留的参考与其他任务的文件均予保留。仍有后续用途、交付核验失败、等待审阅或仅因回复结束、断线而暂停时，维持当前工程。

## 关闭、退休和清理

1. 按本任务过程目录和登记身份确定每个目标。通过所属会话核对真实打开列表、队列、任务状态及弹窗。运行或排队中的任务继续跟踪。未知写入、`needs_reconcile`、占用或未处理弹窗按[原任务状态](../cst-sessions/references/session-operations.md#接续原任务)处理，确认空闲后再收尾。
2. 尚在打开的目标先用所属会话 `close_project(project_id)` 保存并关闭这一个标签。从关闭回执核对 `saved=true`、`tab_closed=true`、`environment_closed=false`，并核对真实打开列表。临时工程会转入 `retired_projects`，核对 `retired=true`。从该 `project_id` 的活动或退休登记读取 `saved_digest`，与实际 `.cst` 的磁盘 SHA256 比对。
3. 已关闭的 `working` 过程工程仍有活动登记时，按[显式退休](../../docs/guides/retire_closed_process_projects.md)核对所属过程目录、原关闭证据、磁盘与登记摘要，确认会话空闲且没有其他登记共用该文件。为显式退休分配新的 `request_id`，另行提交 `close_project`，带 `retire=true`、实际 `expected_digest`、`confirm_idle=true` 和 `review_note`。核对退休登记、`retired=true`、`already_closed=true`、`saved_digest` 和 `files_deleted=false`。此步的空闲确认来自调用方，原生标签的关闭证据来自上一步。
4. 有关闭和退休证据后，解析过程 `.cst` 与同名配套目录的实际绝对路径，逐项确认仍在本任务过程目录内，并与正式文件、保留项和依赖核对。仅删除已确认的目标，确认对应路径已消失。若用户另行要求清理冗余备份或图稿，也逐项核对归属与保留清单。
5. 保留恢复引用以及最小的保存、关闭、退休、删除回执。交付时列出最终路径、配套文件、已做核验、求解状态与实际清理结果。`close_project` 处理单个工程标签，DE 保持打开。只有用户明确要求关闭整个环境时才向所属会话提交 `close`。
