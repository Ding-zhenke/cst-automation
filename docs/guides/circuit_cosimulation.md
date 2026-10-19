# Design Studio 接口与当前边界

当前工作重点已调整为功能完善与 skill 建立，专项实机验收留待后续工程逐步开展；见 [开发重点](../CIRCUIT_DEVELOPMENT.md) 与 [场路联合 skill](../../skills/cst-circuit/SKILL.md)。以下已有证据及未验证边界保持原义。

当前为 `0.2.0.dev0` 开发版。CST 2026.1 已完成纯电路、批准几何/端口和线性 network 定量验证。后续真实线性瞬态联合通过实际时间步、三种负载、两侧端口量、独立局部电场积分和普通网络对照。新运行无插值警告，原警告记录仍保留未验证。分阶段数据见 [时间步复核](../CIRCUIT_TIMESTEP_REPORT.md) 与 [首轮实机记录](../CIRCUIT_LIVE_REPORT.md)。

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
- `transient_cosim` 还检查新三维日志段、实际任务绑定、原生 SUCCESS，以及每个同工程数字离散端口的带 cosim 标签的电压/电流时域曲线和时长覆盖。本次无警告的新线性运行返回 succeeded；原有插值警告仍返回 `unverified`，没有放宽公共证据谓词。不能用 Update 返回、谐波或旧完成日志绕过。与旧目标绑定无法区分的重复运行也保持未验证。
- `reuse="verified"` 尚无实机核验缓存来源，拒绝假定命中，不启动重复计算。
- 本次两离散端口实例已核对坐标、连接、两侧探针方向和加载响应；通用三维 port/mode/reference/polarity、参数映射仍不自动推定通过，`link_em` 返回 `verified=False`。
- 属性、单位、探针方向等无法查询时列入 unknown。单次 `apply` 的 readback_verified 保持 False；本轮 V1 通过的是另行保存关闭重开的一致性验收，不代表任何一次 apply 都已验收。
- `bundle` 当前仅清点依赖并复制到新目录。它不编辑二进制 CST，不自动假定链接已重定位；返回 `portable_verified=False`。服务打包任务会保留副本产物并报告未验证。
- SPICE 仅识别 UTF-8 简单 `.include/.inc` 依赖；`.lib` 区段、动态路径、未知格式及外部 CST 闭包未解析时明确拒绝可搬运性声明。
- 曲线单位来自 SDK Quantity 或明确轴标签；仅 S 参数空纵轴标签可识别为无量纲，其他缺失单位读取失败。电压峰值/RMS、探针方向、FFT 窗口未知时元数据明示 unknown，不自行换算。

二极管/SPICE 非线性、外部 CST 依赖闭包及完整中断恢复仍待验收。`CircuitSemi\\Diode` 是官方类型名称；旧 `CircuitSemiconductor\\Diode` 输入作为别名转换。导入波形的时间采用 SI 秒，Import 的 periodic 参数必须使用小写字符串 `"false"`/`"true"`。

## 实际积分时间与输出采样

常用瞬态任务可通过高层接口配置，不启动求解：

```python
settings = {
    "mode": "transient_cosim",
    "duration": {"value": 40, "unit": "ns"},
    "sampling": {"method": "simulated", "points": 8001},
    "integration": {
        "time_step": {"value": 5, "unit": "ps"},
        "auto_solver": False,
    },
    "max_frequency": {"value": 5, "unit": "GHz"},
    "accuracy": 1e-6,
}
# 已有 transient 任务：
report = app.circuit.configure_transient_task("TR", settings)
app.save()
# 新任务使用 create=True，已有同名任务不会被覆盖。
```

数量转换到工程当前时间/频率单位，不修改全局单位。接口按正确顺序设置区间和采样，读回可查询的任务属性；`points` 在 Simulated 模式下不表示实际记录点数。返回 `internal_time_step_verified=False`、`output_grid_readback="unsupported"`，请求的 5 ps 仍不能证明真实联合采用了 5 ps。该高层组合接口完成离线边界检查，按当前优先级尚未追加组合接口的实机验收。

任务 `properties` 可以设置 `sampling method="Simulated"`，保存全部实际仿真时间点；`SetSweepData` 会将它重置成 Manual，应在设置输出区间之后再选 Simulated。5 ps 的手工绘图点不能证明内部采用 5 ps 积分。

本次真实联合的内部时钟由三维网格及 `Solver.TimeStepStabilityFactor` 控制，三档实际 DS 时间点间距与 EM 日志分别一致为 0.81894/0.40947/0.20474 ps。这些是既有原生脚本的运行证据；以下新封装本轮只做离线验证。

### EM 时间步与每步输出配置

在已打开、已审阅的三维工程上使用：

```python
em_report = app.configure_em_time_settings({
    "stability_factor": 0.5,
    "output_sampling": "every_step",
})
app.save()  # Python 配置接口不自动保存或求解
```

`stability_factor` 是三维允许时间步的无量纲倍数，范围 `(0, 1]`；不接受 bool、字符串、绝对 ps 或大于 1 的因子。稳定步长受网格等条件影响，不能从因子推断实际 ps。`output_sampling="every_step"` 下发 `Solver.AutomaticTimeSignalSampling False`，要求时域信号以每个积分步落盘；`automatic` 对应 True，允许自动降采样。它不设置三维场监视器、探针位置或 DS 采样。需要 DS 全部实际时间点时，另外配置 DS 的 `sampling.method="simulated"`。

两字段均可省略其中之一，省略项不改，空字典会被拒绝。接口只提交一个历史块，不 Reset、不改变求解器类型/单位、不重建、不运行任务，也不修改外部 EM 链接工程。调用方应将它用于支持上述命令的当前三维时域 Solver（既有依据为 CST 2026 六面体瞬态场路样例）；不因此宣称其他求解器已兼容。

返回的 `requested` 与 `native_commands` 是请求记录，`history_submitted=True` 仅表示提交调用返回；`readback=None`、`readback_status="unsupported"`，`readback_verified/internal_time_step_verified/output_sampling_verified/solver_verified` 均为 False。没有伪造 getter；未来工程仍需独立核对实际日志、原始时间点与每步输出。失败时 `EMTimeConfigurationError` 保留阶段和请求；`em_time_configuration_partial` 的 `history_submitted=None` 表示可能部分写入，不自动回滚或重试。缺少 model3d 为 `em_time_unavailable`。

服务只配置保存的调用方式：

```python
job = service.submit("build", project_path="work/circuit-service/reviewed.cst",
    params={"workflow": "circuit", "operation": "configure_em_time_settings",
            "settings": {"stability_factor": 0.5, "output_sampling": "every_step"}})
```

`project_path` 使用服务 workdir 内的工程绝对路径或当前工作目录下的有效路径。对应 MCP 工具名也是 `configure_em_time_settings`，接受 `project_id/project_path/request_id/settings`，不要求 DS task_name。两者都进入唯一 worker 并保存，部分提交失败保留失败审计、消息和工程；成功状态仅表示配置保存，不证明实际时钟或物理收敛。

局部电场沿批准的 P1→P2 路径积分时，CST 定向端口电压采用正的 `integral E dot dl`，不能误称为相反方向的标量电势差。极性依据官方端口/网格电压定义及实际端点读回固定，不通过反号拟合取得一致性。

## 服务和 MCP

```python
from tpc_service import RunService
from tpc_service.circuit import register_circuit_handlers

service = RunService("work/circuit-service")
register_circuit_handlers(service)  # 不打开 CST；仅安装路由
# 已有领域 handler 时默认拒绝；replace=True 显式组合而不覆盖旧路由。
```

`params.workflow="circuit"` 与合法 operation 才进入电路分支；其他任务仍使用原实现。所有 SDK 访问由同一 worker 执行，工作工程/导出路径限制在服务 workdir 内。

MCP 入口为 `cst_mcp.circuit_tools.register_circuit_tools()`，显式注册八个工具，不改用户全局配置。`configure_circuit_transient_task` 将 `task_name/settings/create` 交给 service 的 `build / configure_transient_task`；`configure_em_time_settings` 配置当前工程的 EM 时间控制。两者仅配置保存；实际求解仍须另行明确调用 `run_circuit_task`。注册不创建服务；首个需要队列的调用才启用对应服务路由。`compose_handlers=True` 用于明确与已有领域 handler 组合。预览也遵守已配置的工作目录。

命令行可显式启用：`python -m cst_mcp --enable-circuit --workdir work/circuit-service`。本轮通过独立 stdio 客户端检查 initialize、list_tools 和离线 preview 调用；该传输测试不连接 CST。

所有失败证据可通过服务状态/产物接口查看；`unverified` 映射为任务 failed 和 `circuit_result_unverified`，不会增加新任务状态。`configure` 成功表示写入与保存完成，其 result_summary 的原理图/solver 验证字段仍须分别查看。

完整目标与冻结验收标准见 [设计文档](../superpowers/specs/2026-10-19-design-studio-cosimulation-design.md)。
