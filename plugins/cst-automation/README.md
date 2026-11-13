# CST Automation

十四个按任务读取的通用 skill：会话、建模、EM 仿真、电路、结果、诊断、二极管加载、器件表征、科研绘图、实际工程验证、ADS 数据交接和隔离器设计流程。

版本 0.3.99 的 `cst-results` skill 加入按参数点导出完整复数 Touchstone 与来源清单的流程。对应 Python API 随通用运行库提供，不随纯 skill 插件打包。

先阅读[技能索引](skills/README.md)和[安装与能力说明](docs/guides/codex-plugin.md)。本包包含指令、参考方法及可配置样式；Python 运行库、CST SDK、许可证和目标工程由工作环境提供。

本包不携带设备模型、项目参数、扫描数据、私人工程索引、凭据或自动安装脚本。它不会自动启动 CST、求解、安装依赖或修改全局配置。
