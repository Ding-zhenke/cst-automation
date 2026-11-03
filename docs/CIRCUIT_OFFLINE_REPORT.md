# Design Studio 接口离线阶段交付记录

日期：2026-10-19。开发版：`0.2.0.dev0`。用户批准范围：接口与离线验证，先展示真实参数三维/端口预览，再决定是否建模和求解。

## 已交付

- 版本化电路 schema、安全算术/单位校验、EM 端点/激励校验、原理图 SVG 与连接表。
- 惰性 `setup.circuit`、DS 工程入口、官方对象适配、元件/网络/探针/任务配置与读回入口。
- 独立 `CircuitResult`，显式结果域/run ID/单位，复数 CSV 与元数据；禁止覆盖已有导出或工程文件。
- 指定任务运行契约：目标模式、任务与结果身份、两侧证据、消息/审计、缓存拒绝策略。
- 依赖清点、简单 SPICE include 检查、不可解析依赖阻断、源文件只读的副本 staging。
- 显式服务 workflow 注册、单 worker 执行、失败证据保留、部分构建失败时保存现场与审计。
- 六个显式 MCP 工具及 `--enable-circuit`，预览使用已配置工作目录；默认测试/CI 排除实机用例。
- 三维样例 PNG/SVG、精确几何 JSON 和端口 CSV；全程没有创建 CST 工程。

## 离线验证证据

| 项目 | 结果 | 证据位置（仓库内忽略目录） |
|---|---|---|
| 原有非界面基线 | 484 passed，1 GUI deselected，9 既有警告 | `work/circuit-development/baseline2.log` |
| 完整离线回归 | **540 passed，2 deselected，9 既有警告** | `work/circuit-development/final-tests.log` |
| 新增测试 | 56 项；包含反例先失败后修复 | `tests/test_circuit_*`、各包 `test_circuit_*` |
| MCP stdio | initialize → list_tools → offline preview 通过 | `cst_mcp/tests/test_circuit_tools.py` 与完整回归日志 |
| wheel/sdist | 构建成功 | `work/circuit-development/dist/`、`build-final.log` |
| 独立目录安装/导入 | 四个包全部来自 wheel 安装目录，未加载 CST | `work/circuit-development/wheel-check.json` |
| 制品内容 | 包含类型声明，无 CST 工程/DLL/工作目录产物 | 同上 |
| 新增源码语法 | Python 3.9 语法解析通过；不等于 Python 3.9 运行时实测 | 同上 |

回归使用 `.venv/Scripts/python.exe -B -m pytest -o addopts='' -m 'not gui and not cst_live' -q --basetemp work/circuit-development/final-tests`。后台 stdio 管道在沙箱内无响应，同一有界测试在沙箱外通过；完整离线回归使用已批准的沙箱外执行。没有连接 CST。

项目 `.venv` 的 setuptools 65 不能读取现有 SPDX license 字符串；实际构建改用本仓库 `work/` 中隔离环境，仅读取本机现有 setuptools 84，未修改公共 Python。构建最低依赖更正为 `setuptools>=77.0.3`，依据 [setuptools 官方许可格式迁移说明](https://setuptools.pypa.io/en/stable/userguide/license_migration.html)。安装临时文件和目标目录也全部放在 `work/`。

## 独立审查与修复

只读审查发现五项重要问题：结果导出覆盖工程风险、未解析依赖未阻断提交、已有参数可能被覆盖、EM 链接预览遗漏、部分构建现场未保存。均加入可复现的失败测试后修复，并通过完整回归。另验证局部 SI 属性单位不改变已有全局单位，以及无工程/非法规格在访问 SDK 前失败。

## 明确保留到实机阶段的事项

| 项目 | 当前状态 |
|---|---|
| V0 接口/离线验证 | 已通过上述测试 |
| V1 原理图实机写入、保存重开 | 未运行 |
| V2 电路求解与解析/UI 数值验收 | 未运行 |
| V3 网络协同计算 | 未运行 |
| V4/V5 线性/非线性瞬态双向场路联合求解 | 未运行 |
| V6 真实链接重定位与搬运验收 | 未运行 |
| V7 相关实机故障/缓存/收敛检查 | 未运行 |

NativeAdapter 的任务完成提取仍待实机校准，因此 Update 返回后不会宣称求解成功；保留 unverified 和审计。三维端口/模态/参考映射返回 verified=False。依赖打包当前只有 staging，portable_verified=False；服务任务也明确报告未验证。物理表达式安全求值为局部 SI 数值，原表达式保存在审计；全局参数变化后需显式重新写入属性。

这些状态有意限制当前开发版的宣称范围。详见 [使用指南](guides/circuit_cosimulation.md) 和已批准设计。

## 待审阅的三维样例

坐标单位 mm。所有图和数据来自 `cst_automation.circuit_sample.microstrip_sample()`，不采用视觉估计。

| 实体 | 范围 |
|---|---|
| 基板 | X=[-10,10]，Y=[-5,5]，Z=[0,0.8]；εr=2.2，无损 |
| 地 | X=[-10,10]，Y=[-5,5]，Z=[-0.035,0]；PEC |
| 信号线 | X=[-10,10]，Y=[-1.2,1.2]，Z=[0.8,0.835]；PEC |
| P1 | (-9.5,0,0) → (-9.5,0,0.8)，地→信号线 |
| P2 | (9.5,0,0) → (9.5,0,0.8)，地→信号线 |
| 空气盒 | X=[-15,15]，Y=[-10,10]，Z=[-5.035,10.835]；拟开边界 |

参考阻抗 50 Ω；不预先声称微带线匹配。端口均内缩 0.5 mm，端口间距 19 mm。计划频带 0.1–5 GHz，网格预算 20 万单元。实际端口电压/电流正方向及边界、网格状态在批准建模后读回确认。

预览产物：`work/circuit-preview/2026-10-19/geometry.png`、`geometry.svg`、`geometry.json`、`ports.csv`。geometry.json 的参数 SHA-256 为 `528280a0d3e3e66025ceb4f2074f84329e7ceb6cd9a26e67b9bcb149b4ccd502`。用户批准前，不进行几何创建、rebuild 或求解。
