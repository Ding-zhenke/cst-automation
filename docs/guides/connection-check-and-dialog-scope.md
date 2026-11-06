# Connection Check 与跨进程弹窗：离线诊断依据

2026-11-04。只读本机 CST 2026 官方帮助、安装包文本源码及仓库代码。
未连接/启动/关闭 CST，未调用 SDK、枚举真实窗口/进程、读取工程或改变运行库。
不记录实际器件参数、block 名、矩阵或工程路径。

## 来源证据与当前停止边界

来源会话实测 ParameterSweep.Start 在求解前出现 Connection Check，正文为
“Some disconnected elements were found”，按钮含 Ignore / Select Disconnected Elements。
选择 Select 后 Start 返回 0，且没有新的 HB 结果。窗口属于 DE 子进程，原 DE-PID-only monitor 漏检。
这是来源报告，本会话没有独立复测；0 不能解释为扫参成功，也不能据此推广 Start 的全部返回码。
选中断开元素是诊断分支，不是选择继续求解。

## 1. 可公开查询的 block/pin/net 方法

官方 `VBA_DES/special_vbacommands/blockobject.htm`：

```text
StartBlockNameIteration() -> int
GetNextBlockName() -> name
Reset(); Name(blockname)
GetNumberOfPins() -> int
GetPinName(pinindex) -> string
IsPinConnected(pinindex) -> bool
GetBusSize(pinindex) -> int
GetNumberOfPorts() -> int
GetPortName(portindex) -> string
GetPortIndex(portname) -> int
```

`pinindex` 是 0..GetNumberOfPins()-1；可逐块逐 pin 收集名称、实际布尔连接状态和异常，
生成 disconnected pin 清单。GetNextBlockName 枚举与选块公用有状态对象，需先保存名称列表，
再逐块 Reset/Name，不在活动 SDK 调用中插入这些上下文操作。
不存在可读取引脚的块、读取异常和明确 False 要分别记录，不能都称为断开。

官方 `VBA_DES/special_vbacommands/net_object.htm`：

```text
Net.Reset()
Net.GetNumberOfNets() -> int
Net.GetNetNameByIndex(netIndex) -> string
Net.GetNetName(componentport) -> string
Net.GetNumberOfSubnets(netname) -> int
Net.GetComponentPorts(netname, subnetindex) -> variant array
```

**Net.Reset 是查询前置条件。** 官方说明其取得当前连接拓扑，并丢弃尚未 Apply 的累积变更；
因此应在没有待提交 Net 编辑、且没有活动 SDK 操作的上下文中使用，不能作为无条件插入的刷新调用。
来源会话已实测：未 Reset 时 GetNetName 全空；Reset 后才返回有效网络。
未初始化/旧上下文中的全空只能记为查询未验证，不能生成“全部断开”的结论。
GetNetName 在已正确加载当前拓扑、输入映射正确且查询成功时，对未连接 componentport 返回空字符串；
GetComponentPorts 的 subnetindex=-1 返回整个 net。
componentport 使用官方三项表示（类型、元件名、**port** index）；不能直接把 pin index 填为 port index。
bus 的一个图形 pin 可能含多条电气连接，应另留 GetBusSize/GetBusPortNames 的映射和未知项。
IsPinConnected=True 也不证明该块连接到目标激励网络；独立连在一起的孤岛仍可能触发原生检查。

### 来源补充：逐 pin 核验后的例外范围

来源会话报告已用 Block.IsPinConnected 逐 pin 核对，断开项仅为保留的孤立 3D 模型块；
活动离线矩阵与电路元件的 pin 均查询为已连接，并结合 Net.Reset 后的真实网络读回检查。
本会话未独立复测；该证据不提升为所有网络路径/电气正确性或 HB 求解验收。
保留 3D 块、在 Start 的该次精确窗口中由所属会话选择已核验的 Ignore，是来源报告的处理范围；
不是给全项目断开项新增永久豁免，不授权本会话连接、点击或改拓扑。
先前 Update 等待可能涉及同一警告，仍是待验证解释；必须等待来源实际新 HB Run ID 与结果证据，
不能用现次 pin 查询或 Ignore 计划倒推先前原因已经确认，亦不能把 Start 返回值当作完成证明。

这些 getter 可以支持独立拓扑盘点，但本次未找到一个与原生 Connection Check 完全等价、
一次返回全部断开 block/pin/网络孤岛的公开入口。原生检查是否包含未公开的额外规则仍未知。
GUI 的 `Home > Components > Connector > Block Connections` 有逐块引脚/连线列表；
其 Add/Remove/Apply 会改拓扑，不能将该对话框作为纯只读检查命令调用。

仓库 `cst_solver/circuit/adapter.py` 的 `pins()` 已枚举 pin/port，`inspect()` 已读 Net 拓扑；
目前没有把 IsPinConnected 作为独立完整连接检查输出，也没有据此复制原生 Connection Check。
安装自带 `Library/Python/lib/cstapps/_impl/circuits/drivers/design_studio/read.py` 的
`check_connections` 只是注释掉的示意，不能当作可调用且经过文档校准的 SDK 能力。

## 2. 保留同工程 3D 模型时的排除边界

本次检查的 Block API、MWS/CS Solver Properties 与 Project 帮助中，未找到可直接把一个任意
孤立 self/3D block 从普通 HB/Parameter Sweep 连接检查中排除、同时保证保留同工程 3D 模型的公开开关。
因此不建议猜造 `enabled=False`、`ExcludeFromSimulation`、`IgnoreDisconnected` 等 Block property。
SimulationTask 的 enabled 是任务启用，不是 block 连接检查例外。

`Show frequency domain results` 只控制 block S 参数/拟合结果的显示；`Deembed block` 使用逆物理行为；
二者都不是排除 block 的方法。为消除警告而加终端、地、短路或重连，会改变拓扑，不能当作无影响处理。
同样，Block.Delete 不作为保留 self 3D 模型的安全方案：本次没有官方证据证明其归属/生命周期影响。

官方确有 `DES/userinterface/simulationprojects/mode.htm` 的 **Ignore selected blocks**，
但它用于“Creating New Simulation Projects”时定义生成项目的模型组成；
不是当前普通 HB schematic 的通用 Connection Check 例外，不能把同名功能移植到本问题。
`cstdesignstudioprojectblock.htm` 提到未连接块不参与频率边界的确定，也不等于其被连接检查忽略。

来源窗口的 Ignore 是已观察到的交互选择，但仅能说明 UI 提供继续分支；
本次未核实其后是否继续成功、是否记忆选择、是否作用于所有断开项。
若日后在原工程所属会话明确核验全部断开项都在批准例外集合内，可按明确授权处理该次精确窗口；
不自动把所有未连接 pin 或整个工程纳入豁免。

## 3. 未找到批准例外后静默继续的公开 API

在本次检查范围，未找到 Connection Check 的 per-block allowlist、skip-check setter 或
“已核验孤立块继续”的原生公开方法。该能力保持 unknown，不能从其他模块同名选项推断。

官方 Python `cst.interface.DesignEnvironment.set_quiet_mode(flag: bool) -> None` 明确：
True 会抑制 message boxes；需要用户输入的 dialog boxes 不能被抑制。
`quiet_mode_enabled()` 仅是启用/恢复该状态的 context manager。
文档没有给 Connection Check 的默认答案，也没有说 quiet mode 等同 Ignore；不建议用它绕过检查。
可读 wrapper 仅切换 quiet 状态，不包含按已批准 block 自动选择 Ignore 的实现。

当前 `dismiss_dialogs` 要求精确窗口/进程/按钮等证据，已知错误确认还有创建时间约束；
Connection Check 不应加入宽泛自动确认列表。若未来增加专用批准入口，应同时要求：
当前任务/工程身份、完整原生问题清单、精确批准集合、窗口 pid+creation_time+hwnd+正文/按钮匹配；
问题集合有新增、未知或读取失败立即停止，不把 Ignore 后的 API 返回当作结果验收。

## 4. DialogMonitor 的代码缺口与改进建议

仓库 `cst_solver/dialogs.py`：

- `list_windows(..., pid=...)` 在读取 owner 前按 window_pid==pid 提前过滤，漏掉子进程窗口。
- `DialogMonitor._scan()` 将 DE pid 传给 list_dialogs，随后 `_blocking(..., pid)` 再过滤一次。
  只扩大 EnumWindows 范围仍不够，后一个过滤也需接受经过验证的 scope。
- 已有窗口快照包含 window/owner pid、creation time、class、modal、正文/按钮；
  `host.process_identity` 可读取创建时间，但当前 monitor 没有进程族归属解析器。
- Qt 的 `Connection Check` 不在已知标题词中；无 owner/模态证据的 Qt 变体仍有漏检风险。
  可以增加精确候选标题，但必须保留正文/按钮和归属证据，不能只凭标题自动点击。

建议后续离线实现为显式会话进程 scope，而不是取消 pid 过滤后信任所有 CST 窗口：

1. 根 DE 使用 pid+creation_time；记录实际绑定 worker 的身份，并以被核验的进程祖先链及跨进程
   owner 链扩展候选。仅进程名前缀相同不足以确认归属；同一 DE 多工程时也不能声称已精确归属工程。
2. 先取得候选窗口及 owner/进程身份，再决定匹配 root、已核验 descendant 或显式 worker。
   动态刷新后代；中间进程退出、broker 启动、不完整权限或父 PID 重用时保留 unknown，
   不能只用一个未经创建时间核对的 PPID 数值接上旧进程树。
3. 返回 root_identity、window_identity、owner_chain、process_chain、scope_reason、scope_complete、
   scope_errors；归属未确认的候选可报告 attention_required，但不自动确认/点击。
   枚举权限失败或 scope 不完整不能报告“没有阻塞窗口”。
4. 如获授权处理子进程弹窗，传实际窗口 pid，而非 DE pid；点击前再次核对窗口所属进程、
   创建时间、hwnd、正文和目标按钮。Connection Check 的 Ignore 与普通单按钮 Information 分开。
5. 离线 fixtures 应覆盖：DE 子/孙进程 modal、跨进程 owner、同名但无关 CST 会话、PID 重用、
   根/中间进程退出、权限失败、ownerless Qt Connection Check、窗口读取时消失及超时。
   原始快照与身份链保留，不把 monitor 改进解释为 native solver 验证。

这轮只记录诊断方案，没有改运行代码、实施自动点击或执行上述测试。

## 可引用的本机证据路径

安装根目录：`D:/CST2026/CST Studio Suite 2026/`。

- `Online Help/mergedProjects/VBA_DES/special_vbacommands/blockobject.htm`：IsPinConnected、pin/port/bus getter。
- `Online Help/mergedProjects/VBA_DES/special_vbacommands/net_object.htm`：Net getter、componentport 与未连接返回值。
- `Online Help/mergedProjects/DES/components/block/dialog/block_connections.htm`：GUI 逐块连接列表及修改操作。
- `Online Help/mergedProjects/DES/components/block/parameterlist/properties_solver_mws.htm`、`properties_solver_common.htm`：显示、deembed、模型设置的真实语义。
- `Online Help/mergedProjects/DES/userinterface/simulationprojects/mode.htm`：Ignore selected blocks 仅限生成 Simulation Projects。
- `Online Help/mergedProjects/DES/components/block/import/cstdesignstudioprojectblock.htm`：未连接块不参与频率边界。
- `Online Help/Python/source/cst.interface.html#cst.interface.DesignEnvironment.set_quiet_mode`：用户输入 dialog 不能被 quiet mode 抑制。
- `AMD64/python_cst_libraries/cst/interface/studio.py`：quiet context manager 的可读实现。
- 仓库 `cst_solver/dialogs.py`、`cst_solver/host.py`：PID 提前过滤、monitor 双重过滤及已有身份/窗口证据。
