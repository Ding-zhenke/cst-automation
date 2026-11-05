# 会话普通异常的阶段与受限堆栈

当普通异常进入 worker 的操作异常捕获区时，session_operation_failed 保留原错误分类，
新增 error.details.diagnostics。ServiceError 使用原 to_dict，不改已有保存回执。

诊断字段包括异常类型/模块、message、operation/job_id、stage，以及 OSError 提供的
errno、winerror、filename、filename2。OS 没有提供路径时保留 None，不从上下文猜文件名。
PermissionError 本身不证明锁冲突、杀毒软件、访问权限或其他具体根因。

traceback 每层最多保留最后 12 帧，只含 file/function/line；最多附 3 层 cause/context，
循环或剩余链标为截断。文本最多 4096 字符，截断带标记，省略帧数单独记录。
不序列化 locals、请求 params、模型参数、源代码正文、环境变量或任意异常 __dict__。
异常原文和 OS 路径属于本地审计；对外共享前仍按原有私有数据边界处理。

## 阶段的含义

stage 是最后进入的明确代码边界，不是成功检查点，也不能证明副作用尚未发生。

| 示例阶段 | 表示已进入的边界 |
| --- | --- |
| project.digest_check | 读取并核对已登记磁盘基线 |
| environment.attach_owned / restore_reviewed_projects | 原有身份恢复与经审阅标签恢复 |
| project.open / activate / update_tab_state | 工程打开、激活或登记更新 |
| history.submit_schematic / submit_model3d | 原生 History 执行 |
| project.save_native | 调用原生保存 |
| project.digest_after_save | 保存后读取摘要 |
| project.persist_saved_record | 写回保存登记 |
| checkpoint.write | 写入新成功检查点 |

如果 History 已返回、保存已发生，而 checkpoint 落盘失败，仍不能拿失败 stage 推断
工程未改；同样，stage=project.save_native 也不证明原生保存完成。阶段和受限堆栈须与
原 job、磁盘摘要、保存回执、实际工程与弹窗证据一起分析。

普通异常仍会保留 failed job 和 needs_reconcile，不自动重试、换 ID、重放未知写入或
因文件摘要未变改为 ready。不回写旧 job，不从一次重试成功反推前次故障原因。
诊断不触发额外 CST 调用，也不改变会话恢复、保存或 solver 的验证等级。

操作之外的 journal/state 自身若也无法写入，不能保证故障被记录到同一个受拒绝文件；
此时仍需检查 worker 原有错误输出和持久状态，不以新增诊断宣称审计落盘必然成功。

新代码只影响之后加载的 worker。当前运行会话不热更新；由所属会话确认实际空闲后，
沿原身份和恢复引用加载，保留工程及审计，不能为更新诊断而打断仿真。

主操作与监测异常可能并存；另见[监测收尾与加载代码证据](session_completion_monitor_evidence.md)，避免只依据最终 clear 排除本任务首个监测失败。
