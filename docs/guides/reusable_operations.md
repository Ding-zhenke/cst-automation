# 常用操作：已有入口、证据和剩余缺口

常规状态核查优先用结构化读取。需要回答窗口是另一个操作：能读到求解状态，
不代表已经知道提示含义；提示正文未知也不妨碍报告已取得的 job、日志和 running。
本页不授权启动求解、停止、回答未知窗口或升级 worker。

| 操作 | 可复用入口 / 本次处理 | 证据边界或待开发部分 |
|---|---|---|
| 原任务状态 | 新增 `cst_solver.run_status.inspect_owned_run`，组合已有 job、Model3D getter、PID 弹窗和日志末尾 | 各观察独立带时间，不是原子快照；资源采样未合并，日志尚未认证属于当前 job；无全 DS idle getter |
| 正常停止及复核 | 原所属 `Model3D.abort_solver(timeout=...)`；随后用上述只读核查 | 不增加自动停止入口。返回 True 仅是请求返回；窗口、原调用、DS 范围分别判断 |
| 参数修改 | 会话 `set_parameters` → 所属 `app.update()` → 已授权 `solve` | 已有入口，补直接示例；不是逐点全 Rebuild，也不保证缓存保留 |
| 网格设置及生效 | 原 typed `configure_tetrahedral_mesh/configure_fd_linear_solver/configure_fd_frequency`；新增 `mesh_input.read_saved_options` | 已保存 mesher input 不是实时 getter；需绑定产生该文件的 run，不能由数值设置推断收敛 |
| 冻结结果读取 | 原结果 API；官方 `cst.results.ProjectFile(frozen_path, allow_interactive=False)` | 补冻结/读取契约；当前 `cst_solver.Result` 默认允许交互，不能冒充严格冻结 reader；未新增通用目录复制器 |
| 缓存选择窗口 | `result_cache_dialog.inspect/select/confirm` | Windows UIA，不是原生 CST SDK；0.3.57 已在该精确 Qt 提示完成现场操作链验收，缓存完整性仍未验证 |
| Qt 历史错误确认 | `qt_history_error.inspect/acknowledge`，见[定向确认流程](cst_dialogs.md#qt-history-error-的显式确认) | 仅已审阅的精确错误及 OK；拒绝额外输入，不恢复或重放原任务。离线测试通过，真机未验收 |
| 接受已审阅保存基线 | 会话 `accept_saved_baseline` | 复用已有入口；所属会话报告过真实数值策略保存验收，不等于几何等价或求解合格 |
| 保留 DE 升级 | `begin_native_worker_handoff/finish_native_worker_handoff` | 复用既有受控交接；以当前任务返回、队列冻结、完整空闲证据为准，旧验收不能覆盖新阻塞 |
| 失败 3D 归档恢复 | `begin_model3d_archive_recovery/finish_model3d_archive_recovery`，见[完整流程](model3d_archive_recovery.md) | 从原围栏开始、保留完整失败 paired、正常退出旧 worker 后恢复、换新句柄；结束仍需定向 reconcile，原生未验收 |
| 正式 warning-only EM | 现有 `qualify_saved_em/qualify_exploratory_em` 契约各异 | 严格 warning-only 正式资格入口仍待开发；不得将 exploratory 或短 probe 当成完整 EM/DC/HB 通过 |
| ADS HB | 官方 DE API、`CircuitSimulator.run_netlist`、dataset API | 链接既有 ADS 技能；不把私有器件拓扑/参数抽进通用库；历史数据不认证当前工程 |

## 原任务联合只读核查

在原所属会话合法 SDK 线程上使用已有 `app`，不为核查另行连接/打开工程：

```python
from cst_solver.run_status import inspect_owned_run

report = inspect_owned_run(
    app,
    job_reader=lambda: manager.job(session_id, credential, original_job_id),
    expected_pid=owned_pid,
    expected_creation_time=owned_creation_time,
    expected_project=registered_project_path,
)
```

不要在被阻塞的 SDK 线程再排一个操作来“读取进度”。此时先用已有的
`manager.job/status`、独立 PID 弹窗巡检和保存日志，无法合法调用 native getter
就保留其 unknown。helper 不创建并发 SDK 通道。`ready`、running=False、日志可读、
窗口消失各有范围，不合并成整个仿真已停。所有旧错误、首失败锁存继续保留。

`log` 仅最多 64 KiB 末尾用于进度诊断，返回 complete_file、mtime 和摘要；这不是
完整日志验收器，更不能代替完整技能阅读、全矩阵/全部频率读取。正式资格检查必须
读取完整所需原生证据，不能把诊断末尾当通过记录。

## 有限缓存选项流程

先完成用户要求的结果导出/归档。保留授权已存在时无需重复询问，但仍必须核对
本次窗口完整正文和全部选项。只支持精确的已知英文标题和缓存选项，不支持泛化
Yes/No、删除、覆盖或任意按钮。原 job ID 和 DE 创建身份来自原会话，不写死旧示例。

```python
from cst_solver import result_cache_dialog as cache_dialog

before = cache_dialog.inspect(pid=owned_pid, hwnd=observed_hwnd,
                              expected_creation_time=owned_creation_time)
# Read the complete before snapshot and match existing retention authorization.
selection = cache_dialog.select(before, authorization_note=retention_authorization)
# Separate read: the Select request may return before the radio becomes selected.
selected = cache_dialog.inspect(pid=owned_pid, hwnd=observed_hwnd,
                                expected_creation_time=owned_creation_time)
confirmation = cache_dialog.confirm(selected, authorization_note=retention_authorization)
```

若独立读取尚未 selected=True，只继续只读观察，不重复 Select 或提前 Invoke。
确认后用 PID 巡检复查窗口，再读取**原** job 是否完整返回；未返回不重放、不追加
SDK 写入。进入 needs_reconcile 时遵守原恢复流程。最后从保存结果读取所要求的
Run ID、参数、全复数矩阵和轴，比较归档清单/摘要，才能评价缓存内容。新接口始终
返回 cache_verified=False，不因窗口消失或请求发出而提升证据等级。

超时可能发生在 UIA 动作之后：保留“不确定”，先检查现场，禁止自动重试。
0.3.57 公共封装已在所属工程完成精确 Qt 提示的七控件读取、缓存选中独立读回和
确认，原调用返回后仍保留 cst_dialog_blocked，再经原流程恢复。该操作链不需截图/
坐标或 worker 升级；不推广到未知恢复提示，也不认证缓存完整性。范围见 VALIDATION。

## 参数修改示例

在已绑定工作流及授权范围内，复用同一 project_id：

```python
changed = manager.submit(session_id, credential, parameter_request_id,
                         'set_parameters', {'project_id': project_id, 'values': new_values})
# Wait for this exact job, inspect its outcome and current dependency checks.
# Only after acceptance, submit the separately authorized solve through the session.
```

该操作内部 update，不再添加全 Rebuild；原有工程约束及 EM→HB 门槛仍自动生效。
对于同参数重跑，正 Run ID 也可能覆盖旧数据，先冻结需要保留的旧结果。

## 冻结读取及有效网格输入

冻结包包含 .cst、必要同名结果目录、完整日志、历史、端口映射和参数；记录每个文件
的 SHA256、源 job、输入摘要和原错误。源文件正在变化或被锁定就报告归档未完成，
不能复制一部分后称已冻结。缓存选项确认后，若需要验证原矩阵，应在新求解之前
冻结完整保存副本再读。非交互 reader 直接读仍在 DE 中的原工程可能被 UserWarning
拒绝；保留该失败，不为了读成功回退 interactive。读取冻结文件使用官方 ProjectFile 的
`allow_interactive=False`，不回退到活动 DE 或旧 Run ID。保留全部请求的复数元素、
频率/方向和单位；三点诊断、单自适应轮数据和正式宽带资格分别标记。

```python
from cst_solver.mesh_input import read_saved_options
saved_mesh = read_saved_options(frozen_options_path)
```

这个只读解码器返回全部属性；不将 CAD surface gradation iteration 误作现代 HF Tet
质量优化上限。存储阶数与实际曲率阶数需区分；所属会话报告 automatic 下存储二阶仍
生成三阶，而 fixedorder 后新任务输入/日志为二阶。这不证明低质量警告消失或收敛改善。

0.3.57 公共解码器已由所属会话用于 fresh 输入，维护核对了保存报告中的阶数 2、
日志 orders=[2] 及摘要。原生日志不保证整文件 UTF-8：解码失败保留错误和原始字节，
已知 ASCII 标记可用明确字节模式独立提取并标注范围；不能丢弃乱码后宣称完整读取，
也不能猜测未读到的内容或将编码失败判为无结果。

坏单元定位还要求坏单元列表与网格几何来自同一恢复/生成代次。停止后恢复上一成功
网格可能使当前 bad-element 文件和恢复后的网格不配套；单元 ID 范围有效也不够。
重建质量或索引对应检查不一致时拒绝映射，保留原文件摘要和失败，不能拿旧 ID 归因
到当前材料/二极管。几何质量合格仍不代表局部 RF 精度已收敛。本次仅补这一边界，
不新增定位器或扩大主工程操作范围。

受控交接详见 [native worker handoff](native_worker_handoff.md)；保存基线接受详见
[conversation sessions](conversation_sessions.md#接受已审阅的外部保存)；ADS 复用
[官方 API 工作流](../../skills/keysight-ads-simulation/SKILL.md)。安装插件、磁盘源码版本与
活跃 worker 已加载能力必须分别报告；开发和发布不等待工程数值结果，也不自动升级活跃进程。
