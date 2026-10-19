# CST 弹窗检测与恢复

建模静默约 30 秒时，先读取一次弹窗，不能把进程存活或窗口响应当成任务有进展。

```bash
python -m cst_solver.dialogs --json
python -m cst_solver.dialogs --json --pid 12345
# 兼容旧入口：python scripts/cst_dialog_guard.py --json
```

快照提供 `pid`、`hwnd`、`title`、`body`、`buttons`、`text_readable`、`read_errors`。
Win32 通过有超时的 `WM_GETTEXT` 读取正文，Qt/自绘窗口尝试有 4 秒进程超时的 UI Automation。
`text_readable=false` / `needs_visual_inspection=true` 表示正文没有读到，必须检查实际窗口；
不能把读取失败解释为没有弹窗，也不能猜测正文。
实现依据：[WM_GETTEXT](https://learn.microsoft.com/en-us/windows/win32/winmsg/wm-gettext)、
[SendMessageTimeoutW](https://learn.microsoft.com/en-us/windows/win32/api/winuser/nf-winuser-sendmessagetimeoutw)。

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
