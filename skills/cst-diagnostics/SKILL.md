---
name: cst-diagnostics
description: Use when diagnosing CST discovery or ABI failures, unavailable APIs, stalled calls, native dialogs, failed solves, or ambiguous completion status.
---

# CST 故障诊断

先读[环境与能力](../cst-sessions/references/runtime.md)，取得当前工程、原任务/阶段、配置来源及实际错误，不猜安装位置或 SDK 命令。

| 症状 | 首先核查 |
|---|---|
| SDK 不可用 | doctor 配置、路径、ABI、按需导入及底层 DLL 错误 |
| API/MCP 缺失 | 安装模块位置/版本、签名及显式注册 |
| 调用停滞 | 原 job、日志最后阶段、真实窗口与进程归属 |
| 重连失败 | 原引用、worker、DE 的 PID/启动时间/镜像和工程摘要 |
| 结果异常 | 指定数据文件、运行身份、参数一致性、单位和有效矩阵 |

弹窗读取实际标题、正文、按钮和所属 PID 后再决定动作。超时、关闭窗口或 Python 返回不能独立证明成功。受限进程查询失败不证明 CST 已退出。

恢复按 [cst-sessions](../cst-sessions/SKILL.md)，先查原任务再续做，不重复启动或删除现场。原因未明时列已知证据及具体缺项，不用降低门槛或换旧结果掩盖。
