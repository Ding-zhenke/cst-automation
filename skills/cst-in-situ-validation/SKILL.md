---
name: cst-in-situ-validation
description: Record native CST evidence observed during an engineering task or repair a reusable automation defect encountered in that task.
---

# 在实际工程中验证并迭代

按[完整阅读规则](../README.md#完整阅读规则)读取当前操作对应的章节。

## 操作前

从[所属会话](../cst-sessions/SKILL.md)核对原工程、已授权任务、加载的运行库和当前阶段。沿已有工程步骤观察本次请求所需的配置、保存重开、日志、结果或数值收敛。只有离线测试的接口也可以在本次授权范围内使用，先明确预期读回及出错时保全现场的办法。

## 现场发现问题

保存原 job、首个错误、阶段和工程身份，按[诊断入口](../cst-diagnostics/SKILL.md)查实际消息、日志与窗口归属。SDK 尚未返回、可能部分写入或状态未知时保留现场，由所属会话核实原调用及保存基线。原任务结果明确且现场可核对后，在同一工程继续缺少的授权步骤。若确认同一问题来自通用库，再按[修复可复用缺陷](references/library-maintenance.md#修复可复用缺陷)处理。

## 回馈通用库

需要登记某个接口的实机证据时，按[登记与发布](references/library-maintenance.md#登记与发布)记录实际观测、接口版本和脱敏出处。向用户交付工程结果时，分别列出已经观察到的阶段和影响下一步的具体缺项。额外扫描、拓扑变更及覆盖已有结果按工程授权处理。
