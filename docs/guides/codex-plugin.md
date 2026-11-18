# 构建、安装和核对 CST Automation 插件

仓库与插件使用同一组技能。[技能索引](../../skills/README.md)维护各入口及按需引用。宿主可以自动选择技能，也可在选择器中指定。一个任务可以顺序使用多个入口。首次操作前核实选中的来源，避免与同名用户级技能混用。

## 构建

从仓库根目录运行：

```powershell
& .\skills\keysight-ads-simulation\scripts\invoke_hidden.ps1 -Executable .\.venv\Scripts\python.exe -ArgumentList @('scripts/build_plugin.py')
exit $LASTEXITCODE
```

发行物为 `dist/cst-automation-plugin.zip` 和 `dist/cst-automation-marketplace.zip`。清单模板在 `plugins/cst-automation/.codex-plugin/plugin.json`。构建使用仓库技能、所需资源及其文档依赖，保持相对路径。两份 ZIP 的插件内容相同，根 `plugin.json` 和兼容清单声明相同身份与版本。构建目录由 Git 忽略。

## 首次安装

将 marketplace 压缩包解压到新建的长期使用目录，再注册来源和安装。

```powershell
Expand-Archive -LiteralPath .\dist\cst-automation-marketplace.zip -DestinationPath .\dist\cst-automation-marketplace
codex plugin marketplace add (Resolve-Path .\dist\cst-automation-marketplace).Path
codex plugin add cst-automation@cst-automation-local
codex plugin list --marketplace cst-automation-local --json
```

更新已注册的本机来源时，先解包到新目录、核对身份和版本，再整体替换该来源下的插件目录并重装，防止上版独有的文件残留。保留已注册的 marketplace 路径。安装后核对已启用版本、安装目录和文件内容；切换技能来源时另核对当前对话的实际加载位置。

## 运行与维护

插件提供技能和配套资源。Python 运行库单独安装，MCP 配置与正在运行的 worker 各自管理。CST 和 ADS 的首次原生操作按[执行环境](../../skills/README.md#执行环境)使用许可宿主和后台启动器。维护时分别记录源码、发布包、已安装插件和 worker 的版本及能力。实机证据按实际工程和操作登记。

仓库维护记录存放在 `docs/validation/plugin-history.md`（历史版本）、`docs/RULE_MIGRATION.md`（规则迁移）和 `docs/validation/rule-routing.md`（发布验证）。仓库贡献指南提供相应入口。
