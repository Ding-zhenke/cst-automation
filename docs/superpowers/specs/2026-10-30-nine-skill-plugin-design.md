# 通用 CST 九 skill 插件

用户已批准一个通用插件：cst-sessions、cst-modeling、cst-simulation、cst-circuit、cst-results、cst-diagnostics、cst-diode-loading、cst-device-characterization、cst-figures。

skills/ 是唯一指令源码；插件构建只复制明确列出的公共文件。六个基础 skill 使用可迁移的局部参考资料，新增二极管加载、器件表征、科研绘图三个 skill。共用运行依赖说明由 sessions 维护，绘图样式由 figures 维护。Python 库继续独立提供执行接口，插件不包含 CST SDK、模型、运行数据或自动安装动作。

公共资料重新提炼为接口、符号量和方法；不复制私人项目索引、模型卡、尺寸、频率、功率、偏置、扫描条件、结果或路径。原本机行波隔离器 skill 及其参考文件保持原样。字体、字号、线宽和可配置配色可以保留。

同步已在当前主工作区完成的 EM—电路参数研究：显式 scope/单位/绑定，每点 EM 来源更新与参数一致性检查，批次和工况复数快照，StudyResult 比较及保存读回，当前 run 0 不作历史句柄。该入口会求解；缺少能力时先报告不兼容。保留实机未验收的边界。

选择：在原插件骨架上扩展九 skill。未选择直接复制全部本机 skill（含私人资料和其他仓库依赖），也未选择单一巨型 skill（触发范围过宽、重复加载）。

验收：正好九个可发现 skill；公共包引用完整；明确文件清单及隐私拒绝；可重复构建；隔离宿主发现/安装；新场景能区分加载、表征和样式；私人目录哈希不变。不开 CST、不运行求解、不改全局插件配置。
