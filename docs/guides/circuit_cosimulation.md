# Design Studio 接口与当前边界

当前为 `0.2.0.dev0` 开发版。CST 2026.1 已完成纯电路、批准几何/端口和线性 network 定量验证；真实瞬态联合已实跑，但 DS 采样插值警告尚未消除，严格验收保持未验证。分阶段数据见 [实机记录](../CIRCUIT_LIVE_REPORT.md)。

## 不连接 CST 的使用方式

```python
from cst_solver.circuit import circuit_capabilities
from cst_automation.circuit_sample import preview_microstrip
from cst_automation.circuit_preview import preview_circuit

report = circuit_capabilities()  # 文件发现不等于许可证或实机可用
preview_microstrip("work/circuit-preview/2026-10-19")
preview_circuit({"schema_version": 1}, "work/empty-circuit-preview")
```

`preview_microstrip` 的 PNG 需要可选 `plot` extra；`raster=False` 时仅标准库生成 SVG/JSON/CSV。所有视图来自同一组 bounds/端点坐标，未夸大金属层厚度。端口内缩 0.5 mm 的选择已写入 JSON，因此 20 mm 金属线的端口间距为 19 mm。

## 用户审批后的原理图操作

```python
from cst_solver import setup
from cst_solver.circuit import CircuitResult

app = setup("work/reviewed-project.cst")
try:
    snapshot = app.circuit.inspect()
    # app.circuit.apply(spec)  # 先校验 schema，遇到名称冲突不删除已有对象
    # app.circuit.link_em(block_name=..., source="self", port_map=..., parameter_map={})
    # outcome = app.circuit.run_checked(task_name, mode="transient_cosim",
    #                                  expected_results=[{"tree_path": actual_path, "run_id": actual_run_id}])
finally:
    app.close()

# reader = CircuitResult("work/reviewed-project.cst")
# reader.get_tree_items()  # 再选择真实路径和实际 run ID
```

上例注释表示需要调用方提供真实读回数据，不能把注释中的符号当成有效配置。

schema v1 包含 units、parameters、blocks、external_ports、nets、probes、em_links、tasks；元件属性通过 `property_units` 指定单位，net 端点必须包含 `component_kind/component_name/pin_name`。参数只允许已声明变量和加减乘除，不执行 Python 表达式。已存在三维模块通过 `em_links` 引用，不复制创建自身模块。

物理属性在当前适配器中安全求值后写成 SI 数值，并为该属性选用对应局部单位；不会为了改一个元件而改变已有工程的全局单位。原始参数表达式保存在规格/审计中。**修改 CST 全局参数不会自动改变已固化的元件值**：必须通过 `set_properties` 重新求值写入。参数序列也按每点明确的属性和 expected_results 执行，不冒充原生 DS 参数扫描。

## 当前刻意保留为未验证的能力

- `network` 已校准目标任务新日志、输入完整读回及当前保存曲线的归属。真实路径通常为 `Tasks\\SP\\S-Parameters\\S2,1`；读取 SDK 轴标签单位，S 参数无量纲。run 0 是当前别名，导出 CSV 和审计摘要用于固定本轮数据；已有历史 run ID 不由当前执行证明。
- `transient_cosim` 还检查新三维日志段、实际任务绑定、原生 SUCCESS，以及每个同工程数字离散端口的带 cosim 标签的电压/电流时域曲线和时长覆盖。当前实测有 DS 插值警告，因此依然返回 `unverified`；不能用 Update 返回、谐波或旧完成日志绕过。与旧目标绑定无法区分的重复运行也保持未验证。
- `reuse="verified"` 尚无实机核验缓存来源，拒绝假定命中，不启动重复计算。
- 本次两离散端口实例已核对坐标、连接、两侧探针方向和加载响应；通用三维 port/mode/reference/polarity、参数映射仍不自动推定通过，`link_em` 返回 `verified=False`。
- 属性、单位、探针方向等无法查询时列入 unknown。单次 `apply` 的 readback_verified 保持 False；本轮 V1 通过的是另行保存关闭重开的一致性验收，不代表任何一次 apply 都已验收。
- `bundle` 当前仅清点依赖并复制到新目录。它不编辑二进制 CST，不自动假定链接已重定位；返回 `portable_verified=False`。服务打包任务会保留副本产物并报告未验证。
- SPICE 仅识别 UTF-8 简单 `.include/.inc` 依赖；`.lib` 区段、动态路径、未知格式及外部 CST 闭包未解析时明确拒绝可搬运性声明。
- 曲线单位来自 SDK Quantity 或明确轴标签；仅 S 参数空纵轴标签可识别为无量纲，其他缺失单位读取失败。电压峰值/RMS、探针方向、FFT 窗口未知时元数据明示 unknown，不自行换算。

二极管/SPICE 非线性、外部 CST 依赖闭包及完整中断恢复仍待验收。`CircuitSemi\\Diode` 是官方类型名称；旧 `CircuitSemiconductor\\Diode` 输入作为别名转换。导入波形的时间采用 SI 秒，Import 的 periodic 参数必须使用小写字符串 `"false"`/`"true"`。

## 服务和 MCP

```python
from tpc_service import RunService
from tpc_service.circuit import register_circuit_handlers

service = RunService("work/circuit-service")
register_circuit_handlers(service)  # 不打开 CST；仅安装路由
# 已有领域 handler 时默认拒绝；replace=True 显式组合而不覆盖旧路由。
```

`params.workflow="circuit"` 与合法 operation 才进入电路分支；其他任务仍使用原实现。所有 SDK 访问由同一 worker 执行，工作工程/导出路径限制在服务 workdir 内。

MCP 入口为 `cst_mcp.circuit_tools.register_circuit_tools()`，显式注册六个工具，不改用户全局配置。注册不创建服务；首个需要队列的调用才启用对应服务路由。`compose_handlers=True` 用于明确与已有领域 handler 组合。预览也遵守已配置的工作目录。

命令行可显式启用：`python -m cst_mcp --enable-circuit --workdir work/circuit-service`。本轮通过独立 stdio 客户端检查 initialize、list_tools 和离线 preview 调用；该传输测试不连接 CST。

所有失败证据可通过服务状态/产物接口查看；`unverified` 映射为任务 failed 和 `circuit_result_unverified`，不会增加新任务状态。`configure` 成功表示写入与保存完成，其 result_summary 的原理图/solver 验证字段仍须分别查看。

完整目标与冻结验收标准见 [设计文档](../superpowers/specs/2026-10-19-design-studio-cosimulation-design.md)。
