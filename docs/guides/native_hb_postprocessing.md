# 用代码配置 HB、原生扫描及后处理

这些小接口位于 `cst_solver.circuit.native`，接受已打开工程的
`app.cst_file.schematic`；CST Python 结果模板内也可传 `calling_app`。
导入不连接 CST，配置与曲线写入不启动求解或自动保存。
HB 频率数值沿用目标任务当前生效的频率单位，任务可能启用了局部单位；
调用前先核对单位，本接口不切换单位。原生扫参点沿用工程参数的单位，
表达式引用调用方已经定义的工程参数。示例中的数组由调用方提供，
不包含任何实际模型的参数或扫描范围。

## HB 与原生参数扫描

```python
from cst_solver.circuit.native import (
    configure_hb_task, replace_parameter_sweep_sequences,
)

s = app.cst_file.schematic
configure_hb_task(s, r"RF_Sweep\HB", [
    {"frequency": "pump_frequency", "order": "pump_order"},
    {"frequency": "rf_frequency", "order": "rf_order"},
], diamond=False)
replace_parameter_sweep_sequences(s, "RF_Sweep", {
    "FrequencyDirection": {
        "rf_frequency": reviewed_frequency_points,
        "rf_direction": reviewed_direction_values,
    },
})
app.save()
```

示例要求实际存在的 Parameter Sweep 父任务和 Spectral Lines 子任务。
序列函数显式清除父任务的全部旧序列，不删除任务及其 HB/后处理子任务。
`configure_hb_task(..., create=True)` 只创建新名称，拒绝覆盖已有任务。
错误输入在原生写入前拒绝；原生命令失败可能留下部分配置，保留现场并
检查，不自动重试、回滚、保存或更新全部任务。本模块未增加 HB 求解入口；
运行时继续遵守所在工程的串行调度、空闲检查、原生日志及逐工况验收要求。

box scheme 的混频最高频率可按 `sum(order_i * f_i)` 核对被动数据上限。
HB 还需要被动数据支持 DC。数据覆盖不能替代谐波阶数收敛验证；本接口
不注入固定频段、谐波阶数、端口名称或模型专用的偏置/归一化公式。

## 指定运行的复数谱线与 Results 曲线

```python
from pathlib import Path
from cst_solver.circuit.native import read_spectral_component, write_real_curve

# tree_path 和 result_id 必须先从实际原生结果树读回；不假定 run 0。
component = read_spectral_component(
    s, tree_path, frequency, result_id=result_id,
)
write_real_curve(
    s, r"Results\MyFrequencyResponse\Transmission", output_dir / "transmission.sig",
    measured_frequencies, measured_transmission_db,
    title="Same-frequency transmission at specified RF power",
    x_label="RF frequency", x_unit="GHz", y_label="Magnitude", y_unit="dB",
    values_in_db=True, replace=True,
)
app.save()
```

谱线读取要求唯一匹配，保留复数值；缺失、重复或非有限样本直接报错。
曲线 x 必须严格递增，x/y 长度相同且为有限实数；调用方从同工况、正确
方向的真实输入频率扫描整理数组，不把边带频谱或 Run ID 改名为 RF 频扫。
有限功率同频 b/a 不自动成为泵浦工作点的增量小信号 S 参数。

`replace=True` 表示调用方拥有该结果叶和输出文件；只替换指定叶，不清空
整个 Results，含有子节点的目标会在写入前被拒绝。CST 删除旧叶可能删除关联 `.sig`，因此接口先删除再保存、
再添加；已有 dB 数据通过 `SetLogarithmicFactor(-1)` 禁用再次取对数。
写入返回不等于原生读回或数值验收：原生保存重开后按实际结果 ID 读取，
核对 x/y、单位、点数和数据来源。

## 更新已经绑定的模板，保留其配置

```python
import hashlib
from cst_automation.result_templates import replace_embedded_python_result_template

# 先在 CST 原生打开工程，让归档资源解包。metadata_path 是已核对的现有
# .rtjson，bound_module 是它 template.python_module.path 指向的模块。
receipt = replace_embedded_python_result_template(
    new_template_source, project_resources,
    metadata_path=metadata_path,
    expected_sha256=hashlib.sha256(bound_module.read_bytes()).hexdigest(),
)
app.save()
# 显式关闭、原生重开，再核对内嵌源码摘要、绑定设置和实际结果。
```

只允许指定工程 `Model/DS` 内现有 `.rtjson` 绑定所指向的现有 `.py/.rtpy`，
不修改其设置、不扫描替换全部任务、不调用模板代码、不创建新绑定。
源码仅做静态语法/入口检查，旧模块摘要不匹配则拒绝更新。
在关闭工程的解包目录中替换文件可能在下次打开时被归档内容覆盖；该函数
不能证明工程已打开，调用方须遵守打开后更新、原生保存、重开核验的顺序。
新模板仍可用 `stage_python_result_template` 暂存；首次创建绑定不属于本次封装。

## 自动出图的交付与配置专用检查

用户要求运行父扫描后自动出图时，模型交付必须包含实际绑定，不以脚本、
暂存库、空 Post 任务或预先写好的静态 Results 曲线替代。绑定配置和内嵌
代码须随工程保存，显式关闭重开后取得原生识别证据。只配置模式不运行
EM、DC、HB、网格、扫描或模板评估来补验收；无法完成则报告具体缺项。

新增两个配置专用原生函数，借用所属会话的 app，并始终明确 project_id：

```python
from cst_solver.circuit.native import (
    configure_hb_postprocessing_chain, inspect_hb_postprocessing_chain,
)
app, record = runtime.project(project_id)
report = configure_hb_postprocessing_chain(
    app.cst_file.schematic, parent_task, hb_task, post_task, create=True,
)
# create=True 拒绝同名；create=False 仅接受已有 template 类型 Post。
# 三个名称使用实际完整任务路径，两子任务必须是父任务的直接子项。
# 启用父/HB/Post，并将 HB、Post 相邻放在末尾；保留其他子任务及其启用状态。
runtime.save(app, project_id)
```

配置函数完成后读取原生任务类型、enabled、generic model folder 和实际树
同级顺序。检查函数只读，读取失败直接报错，不用请求值填充读回。
`readback_verified` 仅指这些任务设置；`binding_verified` 和
`reopen_verified` 始终 False。配置函数失败可能留下部分修改，不自动重试。
它们不创建模板资源、不保存、不重建、不启动任务，尚未完成真机验收。

对已有绑定，可在保存前后分别审计明确指定的资源：

```python
from cst_automation.result_templates import inspect_embedded_python_result_template
resources = inspect_embedded_python_result_template(
    project_resources, metadata_path=actual_metadata_path,
    expected_settings=caller_settings, expected_sha256=source_sha256,
)
```

它检查项目内同目录的 `.rtjson`、local_copy `.rtpy/.py` 和 Summary.rpp
精确名称条目、源码静态语法/入口、源码摘要和调用方预期设置。它不解析或
生成未文档化的整个 RPP 格式，也不从 `GetModelFolder(True)` 猜 `_35_0`
等内部后缀。`resource_integrity_verified=True` 只证明资源审计通过；即使
三文件都在，也不能推出 CST 已加载绑定。后续源码替换继续使用要求旧摘要
的 `replace_embedded_python_result_template`，不覆盖其他模板或设置。

### 首次注册尚缺的原生入口

本机 CST 2026 官方 `VBA_DES/special_vbacommands/simulationtaskobject.htm`
文档支持 template 任务创建、SetProperty、MoveInTree 和 GetModelFolder；
`projectobject.htm` 明确规定 DS 的 ResetTemplateIterator/GetNextTemplate
仅在后处理任务运行期间有效。`cst.tbpp` 的 Python 模块处理模板定义和
执行，不提供已核实的首次绑定注册接口。当前文档检索未建立配置专用的
原生导入/注册路径，因此没有发布一个只写三文件却声称成功的 bind API。
这里是能力缺项，不是禁止通用能力公开；一旦取得可验证入口，应提供
首次创建、同名拒绝、摘要受控替换与原生保存重开验收，并显式注册服务/MCP。

模板的参数、方向、探针、指标及图表分组均由调用方决定。使用实际输入 RF
作横轴，缺方向不补零；重复运行只替换本流程拥有的结果叶及输出文件。
有限功率同频 b/a 不等于增量小信号 S 参数。

## 证据与操作成本

优先用代码、日志、结果文件和原生读回验收；仅在接口不足、实际交互对话框
或需要核对实际显示时使用 computer use，避免界面轮询和重复截图。
本轮封装离线验证；底层原生操作来自一个已经完成的实际工程，不能据此
将新封装、其他 CST 版本或其他模型记为已完成实机求解。
