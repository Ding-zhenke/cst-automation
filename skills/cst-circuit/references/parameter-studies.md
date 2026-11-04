# EM—电路参数研究与历史结果

先检查运行库是否具有 CircuitAPI.run_parameter_study、StudyResult 及对应服务/MCP 入口。缺少时报告版本/入口缺项，不把独立改参脚本冒充联动研究。离线测试不等于目标 CST 版本已完成实机验收。

`app.circuit.run_parameter_study(spec)` **会求解和保存**。`cst_automation.circuit_studies.normalize_parameter_study(spec)` 仅作 SDK-free 预检。研究拓扑不变，当前支持纯电路或单个同工程 self EM 块，逐点编排，不是原生 Parameter Sweep。外部 EM、多 EM 块、原生扫参父任务及双向瞬态联合不作为此入口后端。

## 输入与单位

spec 包含 schema_version=1、name、parameters、points、task，需要时附 em。parameters 明确 scope=em/circuit、unit，可有 circuit 的 block/property 绑定。每点完整提供全部有限数值，不自动展开点积。参数值来自当前工程或用户。

全局参数使用已核对的工程原生单位；unit 是声明，不作维度自动推断。已固化属性用 block/property 绑定，由属性 API 换算并读回 SI 数值。原生公式不能仅凭文本当成已解析数值。

task 指已有叶任务、mode=network 及显式 name/tree_path/run_id；普通 HB 叶为 Spectral Lines，不是泵浦小信号入口。EM 参数须附 em.results。执行入口要求当前别名 **run_id=0**，读取后立即固定为工况快照；历史查询不再追随当前 run_id=0。

## 执行与归属

每点：写入并读回参数 → 需要时 rebuild/保存/EM → 核对指定 EM 数据更新 → 电路任务 → 原始复数读取 → 源快照落盘 → 汇总曲线 → 保存。

EM 放行要求指定原生数据文件指纹更新、原生完成状态 SUCCESS，以及结果参数匹配；日志或全目录变化不能替代。无法映射数据文件或确认状态则 unverified。当前 EM 每点重算，不承诺缓存复用。全局参数元数据缺失/冲突不标成功；属性别名以实际 SI 读回归属。

每次调用新建批次，重复参数保留新工况。失败/未验证点保存已有数据、错误及来源，停止后续点；源快照不提供自动断点重跑授权。

## 保存和比较

原生叶：`Results/Studies/<研究名>/<批次>/<结果量>/<分量>/<工况>`。magnitude/real/imag 保留源单位，phase 为包裹角度，不自动取 dB、归一化、展开相位或算器件指标。HB 混频谱轴不改名为输入扫频轴。

完整 study.json、case.json、复数 CSV、源快照和 .sig 位于工程同名结果目录的 `Result/DS/Studies/<研究名>/<批次>`；读取时核对摘要。

`StudyResult(batch_path)` 提供 list_cases(parameters=None)、read_curve(case_id,result_name)、compare(result_name,parameters=None,component='magnitude')、verify_project()。compare 只比较成功工况，单位须一致，不插值拼轴；读取失败点已存数据仍须检查 case.status。

verify_project() 逐点对照保存的原生叶及归档数组，返回 saved_readback_verified；它不关闭或重开 CST，reopen_verified 保持 False。真正关闭重开由工程所属会话在安全时机完成。

搬运时保留 .cst 与同名结果目录，不承诺单个二进制封装全部历史。服务为 study/run_parameter_study，MCP 为显式注册的 run_circuit_parameter_study，复用所属 worker。离线通过不提高 EM/HB、保存重开或器件性能证据。
