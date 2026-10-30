# CST Automation 插件

本插件包含[九个独立 skill](../../skills/README.md)。名称和描述用于选择任务，正文和参考资料按需加载；不要求每次加载全部内容。用户指令、现有授权及目标仓库约定优先。

## 构建

在源码工作区使用授权虚拟环境执行 `python scripts/build_plugin.py`。显式输入清单位于 plugins/cst-automation/package-files.json，指令唯一源码位于根目录 skills/；不扫描整个 docs 或本机技能目录。

生成 dist/cst-automation-plugin.zip 和 dist/cst-automation-marketplace.zip。插件包根目录含 portable plugin.json、Codex 兼容清单、skills、必要文档及 LICENSE。marketplace 包带本地目录清单和同一插件内容。模板目录尚未集齐所有资源，不直接作为安装源。

构建先检查明确文件清单、九个入口、相对引用、机器路径与物理参数字面量，再生成可重复的 ZIP。审阅仍负责发现没有单位的参数、历史结果或错误的通用化；自动检查不是敏感数据识别的完整证明。新增公共文件须更新清单并审阅。

## 本地安装

将 marketplace ZIP 解压到长期保留的目录。先用 `codex plugin --help` 核对宿主支持。以下命令中的 pluginSource 是已解压 marketplace 的绝对路径：

```powershell
codex plugin marketplace add $pluginSource
codex plugin add cst-automation@cst-automation-local
codex plugin list --marketplace cst-automation-local --json
```

安装会写入所选 Codex home 的插件配置和缓存；构建不会安装。测试时设置进程级 CODEX_HOME 指向工作区内独立目录，避免改变日常环境。真实安装后新建聊天或按宿主提示刷新，并检查九个 cst-automation: 前缀入口。已有同名本机入口可保留，选择时核对来源；验证迁移后再决定停用重复入口，不自动删除私人 skill。

## 运行依赖与同步

插件不随包附带 Python 库或 SDK，不硬编码安装路径。真实操作需目标工作区安装兼容 cst-automation、匹配的 CST SDK/解释器和许可；仅已有数据绘图不需要启动 CST。详见[运行环境](../../skills/cst-sessions/references/runtime.md)。

参数研究等扩展要先检查目标运行库的实际 API 与显式注册状态。插件与 Python 包分别发布；没有 run_parameter_study/StudyResult 时应报告缺项，不假造可用性。EM—电路更新、工况快照和保存读回合同见[参数研究](../../skills/cst-circuit/references/parameter-studies.md)。这些方法的离线测试不能替代目标版本的实机验收。

## 内容边界

共享样式可调整宽度、字体、字号、线宽及配色，目标期刊或用户要求优先。只交付当前已有数据或获授权的工作，不因安装插件自动求解或扩大扫描。

模型、器件参数、源条件、工程索引及历史结果留在项目或私人 skill 中。专业行波器件方案与其他领域仓库专用流程不随本包发行。第三方绘图插件按需由原插件提供，不复制其代码或自动安装。

格式依据：[官方插件打包](https://developers.openai.com/plugins/build/plugins)与[官方 skill 指南](https://developers.openai.com/plugins/build/skills)。
