# Circuit Update 异常与后处理运行身份

## 异常返回不等于完成或空闲

`run_checked` 的 update_call_state 记录包装调用的 not_called、calling（提交意图）、
returned 或 raised；execution_returned 仍只在正常返回后为 True。Update 抛错时，
错误为 circuit_task_update_failed，并保留 failure_stage=update_task、异常类型、
原文及原 CircuitError 的 code/details。最终 stage=finished 只表示审计函数已收尾。

异常审计记录调用前/出错后的磁盘摘要，以及父日志的前后摘要、读取错误和可识别的
追加片段。日志被替换或缺失时，不把它当成完整本轮增量。磁盘摘要是观察，不是新保存
回执；父日志内容也不独立证明哪个叶任务完成。不能因 Update 异常就丢弃原始错误，
也不能因为部分曲线存在就把整个任务标通过。

包装调用抛错不证明后台已停止、没有模态框或原生环境仍可写。因此本版不在 except
中直接 save：save_policy=deferred_until_idle、saved=False、execution_returned=False，
会话继续需要核对。所属会话确认空闲并处理未知状态后，独立保存当前原生内存结果；
保留旧失败 job 和日志，不重放整个扫描、不在 API 聊天接管 DE。没有新保存前，离线
ProjectFile 读到的可能仍是旧磁盘基线；这不证明内存里的新结果不存在。

## 从当前请求定位存储结果

CST 官方 ResultTree/GetResultIDsFromTreeItem 返回目标节点已存储的 Schematic:RunID:N；
Project/GetParameterCombination 用正 ID 解析实际参数组合，不支持 Current Run 0。
官方 Python EvaluateParameters 文档只对 all_runs 说明逐轮 result_id 的参数化含义；
不能把 single_run 下的 callback result_id、GetLastResultID 或最大编号作为当前输入的证明。

`cst_automation.result_identity.select_schematic_result_id` 是纯数据选择器。
`cst_solver.circuit.native.resolve_schematic_result_id` 读实际目标节点 ID，并调用显式传入的
`read_parameters(native_id)` 读取存储参数组合。该 reader 的 ByRef/桥接绑定须由调用方
在当前版本验证；库不猜 SDK 包装签名，不用 RestoreParameter 的当前 UI 值代替存储组合。

```python
from cst_solver.circuit.native import resolve_schematic_result_id

receipt = resolve_schematic_result_id(
    calling_app, required_spectral_paths,
    read_parameters=verified_stored_parameter_reader,
    expected_parameters=current_requested_numeric_parameters,
    requested_id=None,
)
native_id = receipt['result_id']
```

required_spectral_paths 必须包括计算所需的全部端口和电压/电流曲线；每一条都必须包含
同一正 Schematic ID。expected_parameters 包含本次频率、方向及其他影响结果的实际
请求数值，名称/单位由调用方实际核对，不在库里硬编码器件条件。

对于 single_run 回调，先用当前请求参数定位：requested_id=None 对所有共有正 ID 查询
实际组合，只有唯一匹配才返回。未知、缺参、非有限值或多个匹配都拒绝；不选最大 ID。
如果调用方已有明确且经核验的固定 ID，可显式传 requested_id；该 ID 不存在或参数不符
时直接拒绝，绝不悄悄换到另一个运行。

旧 gate ID 被父任务复用可以是合法现象；编号不递增本身不是失败，也不证明缓存可用。
参数匹配只证明所查字段一致，不证明模型、依赖、配置、曲线数值或新执行身份；回执中
solver_verified/execution_identity_verified 保持 False。若要接受缓存，还须独立核对完整
输入、依赖及所需原生证据。run_checked(reuse='verified') 仍不自动接受未经证明的缓存。

## 验证来源

本轮根据所属会话报告定位 Update 异常路径，并只读检查其给出的模板源码；原模块确有
允许未枚举正 ID 和取 max 的分支，且未用存储参数组合约束这些分支。此处没有修改该
模块或运行 CST。具体缺点是否由误读旧 ID 造成，仍须所属会话的原生参数/曲线读回确认。

依据本机已安装官方帮助：VBA_DES/special_vbacommands/result_tree_object.htm、
projectobject.htm，以及 DES/analysis/postprocessing/post_processing_template_layout_python.htm。
本接口的离线替身测试不替代真实模板执行或 solver 验收。

## 文档约定的 ByRef 读取入口

[工程绑定的存储参数桥接](project_bound_run_parameter_bridge.md)提供显式会话只读入口，使用 VBA Variant ByRef 避免猜 Python ABI。仅由所属会话在实际空闲后核验；不能据此假定 Post 回调内嵌套宏或 Python ByRef 已通过。
