# Codex 多 skill 插件

一个 `CST Automation` 插件包含四个独立 skill，原有 `skills/` 文件保持不变：

| Skill | 按需使用的场景 |
| --- | --- |
| `cst-modeling` | 几何规划、预览、建模与检查 |
| `cst-simulation` | 对已审阅工程配置并运行求解 |
| `cst-results` | 读取、导出和分析结果 |
| `cst-diagnostics` | 安装、SDK、弹窗与任务故障诊断 |

宿主先获取各 skill 的名称和描述，再按任务读取相关 `SKILL.md`；一个任务可以先后使用多个 skill。不合并四份指令，也不增加要求每次加载全部 skill 的总入口。保持默认自动选择策略，也可在宿主支持的 skill 选择器中明确指定某个 skill。最终选择由宿主和模型决定，插件不提供确定性的关键词路由或逐 skill 的开关。

## 构建

在仓库根目录使用本仓库虚拟环境：

```powershell
.\.venv\Scripts\python.exe scripts/build_plugin.py
```

产物是 `dist/cst-automation-plugin.zip` 和用于本地安装的 `dist/cst-automation-marketplace.zip`。清单源文件位于 `plugins/cst-automation/.codex-plugin/plugin.json`；它是打包模板，该源目录尚未包含 skills，不能直接当成完整插件安装。

插件压缩包根目录含 `.codex-plugin/plugin.json`、`skills/`、`docs/` 和 `LICENSE`；marketplace 压缩包则包含本地目录清单和同一份完整插件。每个 skill 逐字节复制，文档保留原有层级，使 `../../docs/...` 相对引用在插件内继续有效。新增 `skills/<name>/SKILL.md` 后重新构建会自动纳入。`dist/` 已由 Git 忽略，不维护生成文件的第二份源码。

## 使用与边界

在 PowerShell 中可将 marketplace 包解压到一个长期保留的目录，然后添加并安装：

```powershell
Expand-Archive -LiteralPath .\dist\cst-automation-marketplace.zip -DestinationPath .\dist\cst-automation-marketplace
codex plugin marketplace add (Resolve-Path .\dist\cst-automation-marketplace).Path
codex plugin add cst-automation@cst-automation-local
codex plugin list --marketplace cst-automation-local --json
```

这些安装命令会修改当前用户的 Codex 插件配置和缓存；构建脚本本身不会安装插件。保持 marketplace 源目录可用，更新源码后重新构建并更新解压目录，按宿主提示刷新插件缓存。桌面端可在插件目录选择该 marketplace 并安装，具体步骤参见 [官方插件打包与本地测试说明](https://developers.openai.com/plugins/build/plugins)。

本版是纯 skill 插件，不包含 Python 运行库、CST SDK 或自动启动 MCP 的配置。执行指令前，目标工作环境仍需安装 `cst-automation`，真实操作需要匹配的 CST 环境；已有 MCP 服务可继续使用，见 [MCP 使用](mcp-usage.md)。插件文档不能代替运行库，也不能据此声称仿真通过。

原有仓库内与用户级 skill 可继续保留；若宿主同时发现多个来源的同名 skill，应在选择器里核对来源，避免把两份副本当作不同能力。隔离的 Codex CLI 测试已验证 marketplace 发现、插件安装和四个带 `cst-automation:` 前缀的 skill 元数据可见；实际对话中的自动选择和桌面端体验尚需单独验收。
