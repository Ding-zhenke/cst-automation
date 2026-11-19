# CST 原理图坐标帧修复记录

## 实机证据与根因

已提供的原生工程/XML 与 CST 调用回执表明，原理图对象的原生坐标以图纸中心为零点，而 `Block.Position` / `ExternalPort.Position` 使用从零开始的 setter 坐标帧：

| Setter 输入 | 原生 getter/XML 坐标 |
|---|---|
| Block `[175, 300]` | `[-49825, -49700]` |
| Block `[75, 700]` | `[-49925, -49300]` |
| ExternalPort `[25, 550]` | `[-49975, -49450]` |

每轴均有固定 `-50000` 偏移。已有 `MWSSCHEM1` 原生坐标 `[-225, 575]`，与小范围布局相符；新建 `N07` 未指定坐标时则落到 CST 默认 `[75, -24500]`。此前建模规格和移动接口直接把输入传给 setter，且原移动测试的假对象没有模拟 getter 偏移，因此无法发现坐标帧错误。

## 修复

- 新建 Block、ExternalPort 及二极管/SPICE 模型支持 `native_position: [x, y]`。输入按原生 getter 坐标解释，范围严格在 `(-50000, 50000)`；写入前两轴分别加 `50000`。
- 新增移动方式 `set_position(..., coordinate_space="native")`。旧字段 `position`、旧 setter 默认行为和旧 service 调用仍保留，既有请求不被静默重解释。
- 探索性线性 SP 的外部端口创建也支持 `native_position`，旧 `position` 保持兼容。
- 创建回执给出请求坐标、实际 setter 参数、getter 读回及坐标是否相符。缺少 getter 时回执明确标为 unavailable。
- 新原生坐标路由要求 worker 声明 `circuit-native-position-v1`；旧 worker 保留原来的 setter 坐标模式，不会静默按新模式移动。
- 未指定位置时仍由 CST 决定默认值；新的建模与电路技能要求新建对象显式传 `native_position`，避免误用 `[75, -24500]` 一类默认放置。

## 验证边界

基于上述实机数据构造的离线原生接口替身验证了创建及移动方向：例如目标原生 `[-225, 575]` 会写入 `[49775, 50575]` 并读回 `[-225, 575]`。本次没有打开、修改或运行其他会话正在使用的工程，也没有启动 CST。离线测试证明代码按已观测的偏移换算；未重新对真实工程执行创建/移动，未做原生视图的整图可读性验收，也未验证不同 CST 版本是否有不同坐标行为。

专项检查结果：坐标、建模配置、线性 SP、静态 SP、电路 API 与 MCP 工具检查 `178 passed, 1 deselected`；session/service/worker 检查 `84 passed, 2 deselected`。后者排除了需要创建 Windows junction 的用例，该环境拒绝 junction 权限；MCP stdio 子进程集成用例也曾在沙箱中等不到初始化响应，未计入通过数。独立插件包检查 `3 passed`，技能格式检查通过。
