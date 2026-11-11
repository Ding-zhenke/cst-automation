# CST 弹窗检测与恢复

建模静默约 30 秒时，先读取一次弹窗，不能把进程存活或窗口响应当成任务有进展。

```bash
python -m cst_solver.dialogs --json
python -m cst_solver.dialogs --json --pid 12345
# 兼容旧入口：python scripts/cst_dialog_guard.py --json
```

快照提供 `pid`、`hwnd`、`title`、`body`、`buttons`、`text_readable`、`read_errors`。
Win32 通过有超时的 `WM_GETTEXT` 读取正文，Qt/自绘窗口尝试总计最多 4 秒的 UI Automation：
先 Control View，无正文时再 Raw View，每次最多 2 秒；补读 Text/Value pattern。
read_attempts 保留各次正文和失败。Raw View 仍无正文时保持未知，不从 Yes/No 猜语义。
`text_readable=false` / `needs_visual_inspection=true` 表示正文没有读到，必须检查实际窗口；
不能把读取失败解释为没有弹窗，也不能猜测正文。
实现依据：[WM_GETTEXT](https://learn.microsoft.com/en-us/windows/win32/winmsg/wm-gettext)、
[SendMessageTimeoutW](https://learn.microsoft.com/en-us/windows/win32/api/winuser/nf-winuser-sendmessagetimeoutw)。

CST 2026 的 `Quiet/Scripting mode is active and pop up windows are blocked.` 提示表示人工界面处于脚本模式。正文完整且与标题、`Minimize` / `Switch to Interactive Mode` 按钮及同进程 Qt owner 一起匹配时，快照标记为 `scripting_control`，API 巡检不因此锁存阻塞。许可证释放、保存确认及未完整读到的窗口分别按实际快照判断。当前截图无法确认旧回执中未读全的窗口身份。

## 脚本接入

```python
from cst_solver.dialogs import guard, check_dialogs

pid = app.project.pid  # 在执行线程取值，巡检线程不能调用 CST SDK
check_dialogs('建模前', pid=pid)
with guard('build/save', timeout=600, poll=1, pid=pid):
    model.build_all()
    model.save()
```

独立巡检线程在 SDK **尚未返回**时即向 stderr 输出 `[CST_DIALOG]` JSON，并立即 flush。
旧 `with guard(...)` 与 `from cst_dialog_guard import guard` 可继续使用。
合法长求解使用 `timeout=None`，保留弹窗检测；超时但没有弹窗单独报告为 `timeout`。
需要进程外监测时，另开终端运行：

```bash
python -m cst_solver.dialogs --watch --pid 12345
# 测试用有限持续时间：--duration 10；Ctrl+C 退出返回 130
```

线程无法强制取消阻塞的 SDK 调用。**原调用没返回前，不得重跑建模或放行后续写任务。**
默认超时只提供诊断，不杀 CST、不关闭其它会话。

## 处理规则

1. 保存步骤名、错误原文和快照，核对 `app.project.pid` 与窗口 PID。
2. 根据正文决定动作；错误/警告、参数输入、保存/覆盖均需明确判断，不能一律点“确定”。
3. 显式操作可用 `dismiss_dialogs(prefer=('OK',), pid=12345, hwnd=67890)`。
   必须指定当前窗口与完整按钮文字（忽略 `&` 助记符），不按坐标或子串匹配。
   发送有时限，操作前重查归属/文字；`clicked` 只表示消息发出，仍需确认窗口消失。
4. 关闭错误框后，读取原调用的返回/异常、修正失败步骤并验收模型；关闭窗口不等于成功。

默认不点击，也不默认选择“不保存”。自动确认须显式开启 `auto_acknowledge=True`，
且 `(title, body)` 完整命中调用方提供的 `acknowledge_messages` 白名单；还要求是单 OK 按钮的信息框。
保存、覆盖、参数输入、错误/警告不自动确认。自动确认后也保留阻塞证据，要求核查本次步骤。
Qt 的虚拟按钮无法用标准 Win32 Button 发送路径操作，返回 `no_match`/`stale_or_foreign`，须据实际界面处理。

## 历史错误优先代码诊断

默认尽量少用 Computer Use。先读取原会话 job 的异常、`runtime_diagnostics`、CST
消息以及目标 PID 的弹窗快照；文本和归属已完整时，不为同一信息重复截图或开界面。

1. 对 `History Error` 保存报错命令及所属 stage/request，追溯生成它的 Python/API
   或有来源依据的 VBA，并核对本机当前版本官方帮助。以
   `Method or property not found. (DiscretePort.Delete "12")` 为例，本机 CST 2026
   的 `DiscretePort` 帮助未列出 `Delete`；不能由此认定只是端口 12 不存在，也不能
   猜另一个删除方法继续试。帮助位置为安装目录下
   `Online Help/mergedProjects/VBA_3D/special_vbaports/special_vbaports_discrete_port_object.htm`。
2. 如果错误框必须关闭才能让原调用返回，且标题、完整正文、按钮、PID/HWND 已核对，
   可使用已有 `dismiss_dialogs` 指定该窗口、完整按钮文字和 `expected_message`
   完整 `(title, body)` 进行定向确认，再确认窗口消失。错误框不加入后台自动确认
   白名单；若有保存、覆盖或其它选择，按已知授权判断，不能一律点 OK。
3. 读取原调用最终返回/异常，确认现场和保存基线后再修正源代码与失败阶段；原调用
   仍阻塞时不追加 SDK 写入、不重放。会话进入 `needs_reconcile` 时仍遵守会话恢复
   的显式核对规则，不能为绕开它换 request_id 或新建工程。
4. 只有正文/按钮不可读、归属不明、程序化点击返回 `no_match`/`stale_or_foreign`，
   或需要接口无法提供的界面信息时，才升级到 Computer Use；按实际界面核对后处理。
   处理后复查原任务、CST 消息及模型，不把关闭错误框当作修复成功。

新器件用空工程和经审查的建模代码避免继承旧历史；已有失败工程不能靠屏蔽错误、
禁用历史步骤或循环点击 OK 获得验收。此流程复用现有接口，不代表已新增自动修复器，
也不代表该截图对应的真实工程已修复。

## 结果失效弹窗的 API 预处理

精确标题匹配时诊断分类为 `cst_results_incompatible`，仍保留 blocking 和首次
monitor failure。分类不代表已选缓存策略，也不会自动点击。不注册后台自动回答；
显式缓存选择入口见下文。确认后原调用完成及缓存内容可读验证仍是独立步骤，
不能用标题匹配、DeleteResults 或 quiet mode 代替这一链条。

`validate_model` 的 `repeated_snapshot` 仅比较前后观测是否相同，单次读取时为 null。
`message_consumption_verified` 和 `native_run_message_binding_verified` 为 false：
读取不保证清队列，相同文本不能证明是旧消息。保留完整前后原始记录；原生 INFO
也可能说明外部依赖缺失，不能因为数量重复或全部 INFO 自动放行几何。

`Results May Get Incompatible With Model` 表示模型变更将使已有结果失效。
优先在提交变更前通过 CST API 处理结果，减少对 Computer Use 的依赖。
这不是让旧结果在修改后的模型上继续有效。

先根据用户已有指令确定结果保留范围。需要保留的结果先导出或归档，并核验产物；
已有授权足够时继续执行，不重复确认。保留范围仍不明确时，再询问必要的选择。
不能因为用户要求“跳过弹窗”就默认删除全部结果。

| 已核对的接口 | 含义与限制 |
|---|---|
| CST VBA `DeleteResults` | 官方说明为删除当前工程的全部结果；不能据此保证保留结果缓存，也不能等同于弹窗中的第一项。 |
| CST VBA `AskForDeleteResults` | 有结果时显示删除结果对话框，不能用于无交互地绕过提示。 |
| Python `de.set_quiet_mode(True)` | 抑制消息框；官方明确排除需要用户输入的对话框。 |
| Python `de.quiet_mode_enabled()` | 在上下文内开启静默模式，退出时恢复原状态；同样不能保证跳过该多选弹窗。 |

静默模式的调用形式如下，`de`、`project` 必须来自当前对话已绑定的会话，
`vba_code` 是已审阅且获授权的变更代码：

```python
with de.quiet_mode_enabled():
    project.model3d.add_to_history("Reviewed model change", vba_code)
```

需要清理时，在变更前通过已核实的宏执行接口调用 `DeleteResults`；
确认目标工程及 3D/原理图上下文，不能混用两者的清理范围。
不要把结果清理本身写成模型历史步骤，也不要编造 `delete_results()` 等未确认的 Python 方法。
若要求保留缓存，先核对当前版本对应的精确接口和行为，再执行；没有证据时不声称它等价于
“Delete current and parametric results (keep result cache)”。

如果弹窗已经阻塞原 SDK 调用，先记录并处理原任务的阻塞状态；
原调用返回前不追加清理宏、不重放变更。需要界面操作时仍遵守上面的 PID、窗口和选项核对规则。
处理后读取原调用返回值/异常、CST 消息与实际状态，保留弹窗监测。

### Qt 选项的程序化处理证据

现已抽取为 `cst_solver.result_cache_dialog.inspect/select/confirm`，详见
[完整调用及收尾链条](reusable_operations.md#有限缓存选项流程)。这不是通用 Yes/No
回答器，也不处理正文未知的恢复提示。0.3.57 公共封装已在所属工程完成精确提示的
完整七控件读取、选择、独立选中读回、确认及原调用返回核对；原失败继续保留。
缓存矩阵完整性仍未验证，详见 VALIDATION。以下为早期原型的现场证据。

已在真实 CST 2026 Qt 弹窗中通过 UI Automation 读取并核对窗口归属、标题、完整选项
和按钮，程序化选择 `Store current results in result cache`，在下一次独立只读检查
确认该选项 `selected=True` 后再 Invoke 确定按钮。选择可能异步生效，不把选择请求
返回当作已选中。这个流程只适用于归属及语义已核对、且已有结果保留授权的现场。

原 SDK 调用阻塞期间没有追加 SDK 写入；原调用返回后，guard 仍保留
`blocked_by_dialog` 失败证据。继续前读取原任务返回、实际保存历史、几何和工程摘要，
核对现场及会话保存基线后恢复，不能把错误框消失当作整个阶段成功，也不盲目重放。
该现场证明了选项可程序化操作，没有证明缓存内容完整可读或 DeleteResults/quiet
模式能消除提示；不对所有 Qt 弹窗作同样保证。

依据为本机 CST Studio Suite 2026 官方帮助，路径相对于安装目录：

- `Online Help/Python/source/cst.interface.html`：`DesignEnvironment.set_quiet_mode`、`quiet_mode_enabled`。
- `Online Help/mergedProjects/VBA_3D/common_vbaapp/common_vbaappapplication_object.htm`：`DeleteResults`、`AskForDeleteResults`。
- `Online Help/mergedProjects/VBA_DES/special_vbacommands/projectobject.htm`：原理图 `DeleteResults`。
- `Online Help/mergedProjects/3D/common_general/common_general_result_question.htm`：各个删除/缓存/另存选项的含义。

上述原生 API 说明为文档核对结论；它们不因 UIA 操作链通过而获得缓存保留验收，
仓库也没有新增自动清理接口。实际操作以当前安装版本帮助为准，不提高求解验收等级。

## 服务与 MCP

`CstBackend` 默认开启巡检，可配置 `dialog_poll=1.0`、`dialog_timeout=None`。
执行线程保存 DE.pid，监测线程只读该整数。记录新增 `runtime_diagnostics`：

| state | 含义 |
|---|---|
| `clear` | 本次巡检未发现可见阻塞弹窗 |
| `blocked_by_dialog` | 目标 PID 有阻塞弹窗，附标题、正文、按钮 |
| `dialog_detected` | 启动期间任务 PID 尚未知，只提供归属未确认的候选证据 |
| `timeout` | 步骤超时，未发现可见阻塞弹窗，没有取消 SDK |
| `monitor_error` | 检测失败，附结构化错误，不能解释为没有弹窗 |

`attention_required=true` 时 `wait()` 提前返回诊断，Python/MCP 共用。
此时生命周期 `status` 仍为 `running`，用于保持串行/取消语义；必须同时检查诊断，不能继续盲等。
独立监测的变化落盘到任务记录和事件流；确认阻塞的原调用返回后，以 `cst_dialog_blocked`
或 `cst_step_timeout` 失败，防止关闭错误框后假报成功。PID 未确认的候选弹窗不会据此判当前任务失败。

验收分开记录：离线回归、真实 Win32 测试消息框、真实 CST/Qt 弹窗以及 EM 求解是不同层次。
本功能没有改变 EM 求解的既有验收状态。
