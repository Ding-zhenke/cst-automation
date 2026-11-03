# 通用电路参数研究

用于拓扑不变的已有电路：纯电路，或一个同工程 self EM 块＋电路。研究参数不含设备专用假设；结果量由调用方提供真实树路径。第一版是 Python 逐点编排，**不创建、不修改、不冒充 CST 原生 Parameter Sweep**。原生扫参配置仍使用 native_hb_postprocessing.md 中的入口。

## 已有工程上的纯电路示例

以下是通用电阻负载扫描示例，假设已有 Rload 元件、AC 任务和所示结果路径；调用前用 inspect 和 CircuitResult 核对实际名称。这里的数值只是示例，不是用户设备参数。

```python
from cst_solver.circuit import StudyResult

study = {
    'schema_version': 1,
    'name': 'load_scan',
    'parameters': {
        'load': {'scope': 'circuit', 'unit': 'Ohm',
                 'block': 'Rload', 'property': 'Resistance'},
    },
    'points': [{'values': {'load': 50}}, {'values': {'load': 75}}],
    'task': {
        'name': 'AC', 'mode': 'network',
        'results': [{'name': 'output_voltage',
                     'tree_path': r'Tasks\AC\Voltages\Vout', 'run_id': 0}],
    },
}
report = app.circuit.run_parameter_study(study)
reader = StudyResult(report['batch_path'])
all_cases = reader.list_cases()
selected = reader.list_cases({'load': 75})
comparison = reader.compare('output_voltage', component='magnitude')
complex_curve = reader.read_curve(all_cases[0]['case_id'], 'output_voltage')
```

`run_parameter_study` **会求解和保存**。不要把它当配置/预览接口。SDK-free 的 `cst_automation.circuit_studies.normalize_parameter_study(study)` 仅验证输入，不运行。API 输入无自动点积扩展，每个 points.values 完整指定全部参数；允许重复点，每个点具有独立 case ID。

## 加入 EM 依赖

在 parameters 中增加 `{geometry_parameter: {'scope':'em','unit':native_length_unit}}`，在每个 values 中补全几何参数，同时增加：

```python
study['em'] = {'results': [
    {'tree_path': reviewed_em_result_tree_path, 'run_id': 0},
]}
```

几何参数必须已存在。第一版对每个点都进行：参数写入及数值读回 → 几何历史重建 → 保存 → `app.run_checked` → 读取指定 EM 原始曲线 → `app.circuit.run_checked` → 读取指定电路曲线 → 源数据落盘 → 写入比较曲线 → 保存。EM 证据限定到每条指定结果的原生数据文件：通过 ResultTree.GetFileFromTreeItem 读回绝对文件路径，核对求解前后的文件指纹，并要求原生求解状态 SUCCESS。仅日志改变不会放行电路；相同数值重新求解只要具有新文件证据仍可继续。SDK 无法提供指定曲线的文件映射或完成状态时返回 unverified，不退回全目录指纹。已有 self EM 块必须能够从其文件来源唯一对应当前工程；外部 EM、多 EM 块、原生扫参父任务及双向瞬态联合暂不作为此入口的执行后端。

对于普通 HB，task.name 指已有 Spectral Lines 叶任务，mode 仍是 network；不是泵浦小信号接口。AC、S 参数和普通瞬态同样指定已有叶任务，运行证据仍由现有 run_checked 判定，不能因包装成 study 就提高验收等级。未经实机核验的任务类型/版本保持未验证。

有 block/property 的参数通过现有属性 API 做单位转换，并核对 SI 数值；没有 block/property 的参数直接修改相应原生参数表，**数值使用工程原生单位**。unit 是调用者核对后的声明，本接口没有参数维度 getter，不会自动把模型的 mm 改为 m。对先前已被 API 求值固化的元件属性，应使用显式 block/property 绑定，不能期待改全局参数便自动更新这些属性。

## 在 CST 里查看与在代码里查询

每次调用创建独立批次，原生比较曲线位置为：

```
Results\Studies\<研究名>\<批次>\<结果量>\magnitude\p0001
Results\Studies\<研究名>\<批次>\<结果量>\real\p0001
Results\Studies\<研究名>\<批次>\<结果量>\imag\p0001
Results\Studies\<研究名>\<批次>\<结果量>\phase\p0001
```

同一分量的其他工况以 p0002、p0003…并列，标题带实际研究参数。选择或添加这些曲线即可比较。magnitude/real/imag 沿用源单位，phase 为包裹相位（deg）；不自动取 dB、归一化、展开相位、算隔离度或拼接 HB 谱线为 RF 扫频。保留原生任务结果；由本接口写入的汇总叶以批次名唯一，不覆盖旧结果。

完整归档位于：

```
<工程同名目录>/Result/DS/Studies/<研究名>/<批次>/study.json
<同一批次>/p0001.sources.json          # 写图前源快照
<同一批次>/p0001/case.json             # 参数、原始复数数组、单位、EM/电路证据
<同一批次>/p0001/<结果量>.csv           # x、实部、虚部
<同一批次>/signals/.../*.sig           # 原生汇总曲线的数据文件
```

case.json 的摘要固定在批次清单里；读取时校验。无 block 绑定的全局参数必须与原生结果元数据中的数值相符，缺失/冲突则保留数据并标为 unverified；支持数值字符串，不把表达式当已解析数值。block/property 绑定的研究别名无需出现在原生参数表中，其归属使用实际属性的 SI 读回证据。源 run_id=0 只是当时的当前别名，历史查询读取归档，不再追着当前 run 0 取数。相同参数重复运行会保留新 case 或新批次。某点失败/未验证时保存已有数据和错误，并停止后续点；不自动重跑或清理现场。源快照用于写图阶段意外中断后的检查，不提供自动断点重跑。

归档本身放在工程结果目录中；搬运时保留 .cst 及其同名结果目录。**尚未实机验证全部 .sig/JSON/CSV 都被单个 .cst 二进制封装**，因此不承诺只拷贝 .cst 就能迁移全部历史。

`StudyResult.compare` 只比较成功工况，支持参数精确过滤和 magnitude/real/imag/phase，单位不一致时报错，不插值或合并不同坐标。`read_curve` 可读取失败点中已保存的原始数据，必须同时检查 case.status。

## 验证与服务

`StudyResult(batch_path).verify_project()` 使用新建的结果读取器，将保存的原生汇总叶与归档数组逐点对照。返回 saved_readback_verified、checked 和 errors；它不关闭或重开 CST，reopen_verified 保持 False。真正的原生保存→关闭→重开→再核验，须由拥有该工程的持久会话在安全时机完成。本轮离线测试不代表该步骤已执行。

服务：`kind='study', params={'workflow':'circuit','operation':'run_parameter_study','spec':study}`。MCP：显式注册后的 `run_circuit_parameter_study(project_id/project_path, spec, request_id)`。沿用唯一 worker、工程目录约束和失败报告，不触碰全局 MCP 配置。直接 Python 调用须遵守同工程串行访问规则。
