# cst-automation 与领域包的公共接口

## 2026-10-26：原生 HB 扫描与后处理代码接口

- `cst_solver.circuit.native` 接受已打开工程的原生 `schematic`（也可使用 CST 模板的 `calling_app`），不加载 SDK、不启动求解、不自动保存。`configure_hb_task(schematic, task_name, tones, *, diamond=False, create=False)` 配置 Spectral Lines 的基频/阶数表达式；`replace_parameter_sweep_sequences(schematic, task_name, sequences)` 显式替换已有原生 Parameter Sweep 的全部序列，保留任务及其子任务。HB 频率数值沿用目标任务当前生效的频率单位（可能为局部单位），不切换单位；扫参点沿用原生参数单位，字符串表达式原样保留。调用方必须先核对单位。
- `read_spectral_component(schematic, tree_path, frequency, *, result_id, rtol=1e-10, atol=1e-8)` 按显式原生结果 ID 提取唯一匹配的复数谱线，不回退到最后一次或 run 0。`write_real_curve(schematic, tree_path, signal_file, x, y, *, title, x_label, x_unit, y_label, y_unit, values_in_db=False, replace=False)` 写入原生 Results 曲线；替换时先删除旧叶再保存 `.sig`，防止 CST 删除关联文件。数值/路径预检先于原生写入；已转为 dB 的数据禁用再次取对数。
- `cst_automation.result_templates.replace_embedded_python_result_template(template_source, project_resources, *, metadata_path, expected_sha256)` 校验已绑定 `.rtjson` 指向的现有 Python 模块并替换源码，保留绑定设置；使用旧模块 SHA-256 检测并发变化。只处理指定工程 `Model/DS` 内的现有绑定，不创建绑定、不修改元数据、不安装全局库。必须在原生工程打开、资源解包后调用，再显式原生保存、关闭重开核验；返回 `native_save_required=True`，不能把资源文件更新当作工程已保存。
- 本轮封装用离线回归验证；底层操作来自已完成的实际 HB 工程，封装本身未新增实机求解验收。详见 [代码方式配置 HB 与原生曲线](guides/native_hb_postprocessing.md)。无新增 service/MCP 操作，现有运行契约与接口保持兼容。

## 2026-10-23：原生 Gyrotropic 铁氧体（仅离线验证）

- `setup.create_material_gyrotropic(name, epsilon, *, larmor_omega, gyrotropic_omega, damping, bias_direction=(0,0,1), mu_infinity=1, kappa=0, color=None, colour=None)` 创建 Normal 类型、磁 `DispModelMu "Gyrotropic"` 的饱和偏置铁氧体。采用 SI 输入模式；两个 omega 参数为 **rad/s 角频率**，从普通 Hz 转换需 `2*pi*f_hz`。材料频率刻度固定为 Hz（基本 1/s 刻度），不改变模型参数的角频率含义、不改变工程全局单位。`DispCoeff1Mu/2Mu/3Mu` 分别为 Larmor 角频率、旋磁角频率及无量纲阻尼，`DispCoeff4MuX/Y/Z` 为无量纲单位偏置方向。
- 物理参数及方向分量均接受有限实数或 CST 参数/表达式字符串，原样写入，不在 Python 中求值。常量频率、阻尼及电导率必须非负，高频相对磁导率为正；纯数值方向需为单位向量。含表达式的方向由调用方保证求值后归一化，常量范围与参数存在/单位/扫参范围需调用方负责。
- 输入完全校验后只提交一个 `Material: <name>` 历史块，不自动保存/rebuild/选择求解器/读回/求解。此模型的 T 求解器材料路线有官方瞬态示例依据；本轮接口仅离线验证，不等于实机验收。它不是任意九项张量公式，不支持时间变量 `t` 或 Tensor formula 的频率占位符 `f`：原生模型自身生成频率响应，输入表达式应引用已定义的项目参数。
- 无新增 service/MCP 操作；标量色散和完整 Tensor formula 接口不变。用法、原生命令依据与边界见 `docs/guides/material_tensors.md`。
- 偏置场来源选择沿用 CST Reset 默认值，不调用来源导入或来源切换。官方 Help 没有给出 `SetMagnetostaticDepSourceField` 切换 Automatic/Homogeneous 的明确枚举；已有磁静态场源的工程须核实实际使用 Homogeneous field 后才能依赖所给方向。本轮没有把该来源模式记为已验证。

## 2026-10-23：复数磁导率张量材料（仅离线验证）

- `setup.create_material_tensor(name, epsilon, mu_tensor, *, mu_imag=None, color=None, colour=None)` 创建 `Tensor formula` 材料。`mu_tensor` 是严格的 3×3 list/tuple，元素为有限实数、Python 复数常量或 CST 实部表达式字符串。`mu_imag` 可选，为相同形状的有限实数/表达式矩阵，表示数学虚部；提供时 `mu_tensor` 不得包含复数，避免重复指定。`epsilon` 是标量实数或 CST 表达式，写入介电张量的三个对角元。
- 输入约定为 `mu = real + j*imag`；CST `TensorFormulaImag` 接收负虚部，接口自动取负。字符串原样保留（虚部仅外包取负），不经 Python 求值。`f` 为材料公式内的频率，单位始终为 Hz；项目参数应由调用方先定义，并使用一致的 SI 频率数值。离线检查不解析 CST 表达式语义或核实参数存在。
- 本机 CST 2026 Help `mergedProjects/3D/special_struct/special_struct_layer_parameters_general.htm` 明确限定 `Tensor formula` **仅用于四面体网格的通用频域求解器，不支持 T/Transient 求解器**。命令、0..2 索引和负虚部约定见 `mergedProjects/VBA_3D/special_vbalayer/special_vbalayerolayer_object.htm` 的 Tensor Formulas。接口不切换求解器；创建历史不表示求解器兼容性已实机验收。
- 完整校验后以一个 `Material: <name>` 历史块提交；不自动保存、rebuild 或求解。原有标量材料入口保持兼容。本扩展仅增加 Python 方法，无新 service/MCP 操作；`readback_verified=False`、`solver_verified=False`。

## 2026-10-21：CST Python 后处理模板暂存（仅静态检查）

- 本机 CST Studio Suite 2026 帮助确认：Design Studio 的 `Post-Processing` 任务可在每次求解后执行模板；扫参/优化会对非插值求解的参数组合执行。Python 模板是位于库根 `Result Templates/<group>/<name>.rtpy` 的单文件模块，必须实现同步顶层 `define()` 与 `evaluate()`。本地依据：`C:\SOFTWARE\CST Studio Suite 2026\Online Help\mergedProjects\DES\analysis\postprocessing\templatebasedpostprocessing.htm`、`post_processing_template_layout_python.htm`。
- `cst_automation.result_templates.validate_python_result_template(source)` 只解析语法和入口签名，不导入或执行模板。`stage_python_result_template(template_source, library_root, *, group, name)` 将 UTF-8 `.py`/`.rtpy` 源文件复制到 `library_root/Result Templates/<group>/<name>.rtpy`；拒绝不安全路径片段、缺失入口及覆盖已有文件，并返回摘要和 SHA-256。
- 静态签名检查拒绝默认参数及仅限位置参数，遵守 CST 按关键字注入入口参数的调用方式；暂存目标解析目录连接后仍须位于库根内，service 的库根也必须位于 workdir 内。
- `build / stage_postprocessing_template` 服务操作和 `stage_circuit_postprocessing_template` MCP 工具将源文件限制在服务 workdir，输出固定到 `workdir/cst_template_library/Result Templates/...`，不打开或修改 CST 工程。用户需在 CST 库设置中加入返回的 `library_root`，创建/选择 Post-Processing 任务并在模板对话框中添加该模板一次。之后由 CST 在每次相应求解后运行模板。
- CST 2026 的帮助为 `SimulationTask.Type` 列出任务类型，但没有记录通过该对象配置 Post-Processing 模板步骤的调用；本接口不伪造自动绑定能力。暂存和静态检查不证明模板能读取目标 HB 结果、CST 已绑定任务或求解后图线已更新；`native_cst_binding_required/readback_verified/solver_verified` 保留真实边界。

## 2026-10-20：通用任务与非线性配置扩展（仅离线检查）

以下为 `0.2.0.dev0` 的新增配置协议，均不自动 rebuild、运行或提高验证等级。

- `configure_transient_task` 的 `integration` 增加 `stepping=automatic/adaptive/fixed`、`method=adams/gear`、整数 `order=1..4`、带 value/unit 的 `minimum_time_step`。省略项保持原设置；仅提供 time_step 时兼容原行为，选择 fixed。automatic 与显式时间步冲突；minimum_time_step 仅用于 adaptive，且不大于最大 time_step。算法、阶数及时间步是请求配置，真实联合时钟仍由实际运行证据判定。
- `CircuitAPI.configure_task_ports(task_name, ports)` 配置已有 transient 任务的外部端口。ports 为非空映射，键为实际 ExternalPort 名称。每项 `source_type=voltage/current/none`；激励端口要求 `signal`，支持 `type=sine`（带单位 amplitude/frequency，可选 offset/delay）或 `type=import`（file、布尔 periodic，默认 False）。Voltage 可提供 resistance 数量；Current 暂不提供内阻配置。none 要求 `impedance={real: 电阻数量, imag: 可选电阻数量}`，并清除旧激励。全部输入和文件在第一次写入前检查；名称不存在、任务类型错误时不写入。
- Import 文件使用两列 CSV：SI 秒及 V/A，至少两个有限实数点，时间非负且严格递增。不在接口中隐式缩放文件。原生 Import periodic 使用小写字符串。返回文件绝对路径和配置时 SHA-256，不声称后续依赖搬运或求解身份已验证。Sine 的单位转换到已有工程单位，保留全局单位。
- `CircuitAPI.configure_nonlinear_model(block_name, settings, *, create=False)` 配置已有兼容类型块；create=True 仅创建新名称。`kind=berkeley_diode` 使用 `parameters` 中的常用 SPICE 名称 IS/N/RS/CJO/TT/BV/IBV/VJ/M/XTI/AREA。IS/RS/CJO/TT/BV/IBV/VJ 为带 value/unit 的数量，其余为无量纲数值；未提供参数沿用模型自身值，不注入样例默认值。新建模型先选原生 enum 2，再写参数；已有块须能读回为兼容 Berkeley 模型，仅改提供的参数，避免重新选择 Model Type 重置其余值。最后读回值和单位；身份继续由原生参数模式标注，不伪造枚举 getter。
- `kind=spice` 要求 file、model，dialect 可选 AUTOMATIC/SPICE3/PSPICE/HSPICE。只提供文件型子电路配置，不自动生成器件模型或猜测引脚；改变模型可能改变引脚，返回前后 pins 供调用方重查连接。文件需存在且可读，返回配置时摘要和原生 file/model/filter/属性；模型名差异不做去前缀等宽松归一化。新增纯数据规范化入口位于 `cst_automation.circuit_models`、`circuit_ports`，不加载 CST。
- 上述新方法返回 requested、readback、readback_verified=False、solver_verified=False，不能完整查询的信号参数/阻抗保留 unknown。原生部分写入或读回不一致为 `circuit_build_partial`，保留请求、阶段和失败现场，不自动重试/回滚。Python 调用后显式 save。
- service 新增 `build / configure_task_ports`（task_name/ports）及 `build / configure_nonlinear_model`（block_name/settings/create）；文件输入受 service workdir 约束，在打开 CST 前检查。均在唯一 worker 配置并保存，失败沿用部分工程及审计机制。对应显式 MCP 工具 `configure_circuit_task_ports`、`configure_circuit_nonlinear_model`，电路工具增至十个。原有求解入口及证据判据不变。

## Design Studio 电路扩展（0.2 开发接口，分阶段实测）

用户已批准 2026-10-19 场路联合设计及真实几何/端口预览；本轮已分阶段实测。具体通过范围和未通过项以 `docs/VALIDATION.md`、`docs/CIRCUIT_LIVE_REPORT.md` 为准。

- `cst_automation.circuit_schema.validate_circuit_spec(spec)` 返回独立、规范化的 JSON 规格；数值元件属性须附显式单位，表达式仅允许安全算术与已声明参数。
- `cst_automation.circuit_preview.preview_circuit(spec, output_dir)` 离线输出 SVG、连接表、参数与输入摘要，不加载 CST。
- `setup.circuit` 为惰性 `CircuitAPI`；`setup.new_circuit_project()` 创建 DS 工程。现有三维接口默认行为不变。
- `cst_solver.circuit.circuit_capabilities(probe='static', app=None)` 静态发现不加载 SDK；live 仅使用显式传入的会话。发现、离线验证、实机读回、solver 验收分别报告。
- `CircuitAPI` 提供 `inspect/list_block_types/list_pins/apply/set_properties/configure_transient_task/validate/link_em/inspect_dependencies/bundle/run_checked`；仅运行指定任务，不运行所有任务。
- `CircuitResult(path)` 选择 `get_schematic()`，读取结果必须显式指定实际树路径和 run ID；复数 CSV 分实虚列并附元数据。
- CST 2026 实测电路树路径为 `Tasks\\<task_name>\\...`；任务筛选/运行同时兼容原先离线规格的 `<task_name>\\...`，不改写返回的真实路径。结果原始数组无 Quantity 时，单位读取 SDK 的轴标签；仅明确的 S 参数树及空纵轴标签可识别为无量纲，其他缺失单位继续报错。
- `run_checked(task_name, *, mode, expected_results, reuse='never', note='')` 区分 `network` 与 `transient_cosim`，缺目标执行、模式、归属或两侧耦合证据时返回 `unverified`。未实测的证据提取不得推定成功。
- `register_circuit_handlers(service, *, replace=False)` 显式安装路由；已有 handler 默认冲突，显式 replace 时组合旧路由。`params.workflow='circuit'` 才进入电路实现。`build` 对应 configure/configure_transient_task/configure_em_time_settings/inspect/read_results/package，`solve` 对应 run_task，`study` 对应 parameter_sequence。
- `RunService.register_workflow(workflow, handlers, *, replace=False)` 原子注册按 workflow 分流的 build/solve/study handler；显式 replace 允许与已有领域 handler 共存，未匹配 workflow 的任务仍走原 handler，不读取/覆盖其私有状态。
- 保留现有任务 kind/status；电路 `unverified` 映射服务 failed，错误 `circuit_result_unverified`；失败返回可携带 artifacts/run_identity/result_summary/saved，旧默认值不变。
- `cst_mcp.circuit_tools.register_circuit_tools()` 显式注册八个工具；SDK 操作一律进入唯一 worker。预览写文件也限制在服务工作目录。
- 错误码：`circuit_unavailable/spec_invalid/topology_invalid/mode_unsupported/dependency_missing/build_partial/result_unverified/result_read_failed`（每项完整前缀 `circuit_`）。
- 对 SDK 尚不能可靠查询/重定位的属性、依赖或任务完成状态，明确报告 unknown/unsupported，不能以缓存或空值替代。
- 二极管原生类型为 `CircuitSemi\\Diode`；保留离线阶段的 `CircuitSemiconductor\\Diode` 作为兼容输入别名，创建时转换为原生名称。列出类型不代表其非线性求解已经验收。
- CST 2026 内置 `Diode` 的 Berkeley SPICE 模型（请求枚举 2）使用原生完整参数枚举读回。`inspect` 为该块增加 `property_metadata`（实际类型和 `GetUnitForProperty` 单位）及 `model_identity`。身份仅在原生类型及十五项名称/类型完整匹配时返回 `{name: 'Berkeley SPICE', evidence: 'documented_native_property_schema'}`；这不是原生枚举 getter。`set_properties` 的 `Model Type` 返回 `{requested_enum: 2, model_identity: ...}`，不把请求值冒充读回值。其他二极管模型、缺项、额外项、重复项、类型或单位读取失败均保留 unknown/报错，不能提升运行证据等级。普通参数仍返回实际原生值。
- 同一次内置二极管属性写入总是先切换模型，再写普通参数，最后统一读回最终状态，与输入字典顺序无关。显式单位 `1` 只有在原生单位确为空时才按无量纲数值写入，不调用局部单位 setter；读单位失败不会当作无量纲。
- 原生文件型 SPICE 块的 `inspect` 另外读回 `spice_model`、`spice_filter` 及完整可枚举属性/类型/单位；模型名不可读、空模型名、枚举失败均进入 unknown。没有可读取外部文件的内嵌 SPICE 源码尚未校准，保持 unknown。外部模型文件摘要与依赖清点另记，选中模型名不代表文件搬运或器件等价已经验收。
- `run_checked` 在任务执行后重新清点外部文件依赖，与提交前的绝对路径和 SHA-256 比较；缺失、变化或无法完整清点时不得 succeeded。工程自身保存会改变二进制文件，不参与外部文件摘要比较；其项目路径和实际输入读回仍由既有执行证据检查。
- `CircuitAPI.configure_transient_task(task_name, settings, *, create=False)` 配置一个明确的瞬态任务，不执行求解。`settings` 包含 `mode`（network/transient_cosim）、带 value/unit 的 `duration`，可选 `sampling={method: simulated/manual, points: 整数}`、`integration={time_step: 数量, auto_solver: 布尔}`、`max_frequency` 数量及 `accuracy`。数值转成工程当前时间/频率单位，不改全局单位；先 `SetSweepData(0, duration, points)`，最后才设置采样方式。积分步长是请求值，返回 `internal_time_step_verified=False`；Simulated 的 points 只用于设置区间，不代表实际点数。实际采样和内部时钟仍须从运行证据确认。
- `create=True` 只创建不存在的目标名；默认仅配置已有 transient 任务，拒绝其他任务类型和名称冲突。返回实际可读任务属性与单位，输出网格点数不能完整查询时不声称全量读回已验证。部分写入失败使用 `circuit_build_partial`，清除依赖缓存并保留现场。
- 服务显式增加 `build / configure_transient_task`，参数为 `task_name/settings/create`；对应 MCP 工具 `configure_circuit_transient_task` 显式注册到同一 worker。配置任务只写入保存，不自动求解，不改变 `unverified` 的服务映射。
- `setup.configure_em_time_settings(settings)` 配置当前工程三维 transient Solver 的时间步及落盘采样，不修改 DS 任务或外部链接工程。`settings` 为非空字典，可含 `stability_factor`（有限数字，`0 < factor <= 1`，拒绝布尔/字符串）和 `output_sampling`（`every_step` / `automatic`）；省略字段保持不变。稳定因子为无量纲倍数，不接收绝对时间步。两字段分别生成 `Solver.TimeStepStabilityFactor` 与 `Solver.AutomaticTimeSignalSampling False/True`，通过一次历史块提交；不 Reset、不切换求解器、不重建、不保存或求解。
- 返回 `requested/native_commands/history_submitted/scope`，其中 scope 为 `current_project_model3d`；无可靠原生 getter 时 `readback=None`、`readback_status='unsupported'`，`readback_verified/internal_time_step_verified/output_sampling_verified/solver_verified` 全为 False。成功提交历史不代表设置读回、实际时钟或每步输出已验收。参数错误在访问工程前抛 ValueError；没有 model3d 抛 `EMTimeConfigurationError(code='em_time_unavailable')`；历史提交失败为 `em_time_configuration_partial`，保留 requested/native_commands，可能部分写入，不自动回滚或重试。
- 服务新增 `build / configure_em_time_settings`，只接受上述 settings 并在打开工程前检查，经唯一 worker 调用 setup 方法并保存；部分提交失败映射 `circuit_build_partial`、保留现场审计。新增显式 MCP `configure_em_time_settings`，参数 `project_id/project_path/request_id/settings`；不含 task_name，不自动提交求解。电路工具总数增为八个。适用的 EM Solver 命令依据本机 CST 2026 官方帮助与既有脚本；本次组合封装只做离线验证。
- `bundle` 先显式保存工程；副本不包含工程根目录的会话锁 `Model.lok`。其他复制错误仍保留失败产物并报错。返回的 staging 标志不自动提升为链接搬运验收通过。
- 实机兼容修正：`set_units()` 使用 CST 2026 的 `Units.SetUnit`，不下发 `Reset/Length`；温度别名 Celsius/Kelvin/Fahrenheit 对应 degC/K/degF，电路量单位由关联 schematic 设置。`create_discrete_port` 使用明确坐标（非拾取点）及官方 `Voltage/Current` 命令；CST 无 `DiscretePort.Folder`，非空 `folder` 在提交前报错，空默认值不下发该命令。
- 运行记录保留消息原始对象；明确的 `type=INFO` 是信息，警告、错误或无法识别的非空消息仍要求审阅。电路原生完成证据须同时包含本次指定任务的新日志段、必要输入完整读回且一致、该任务保存后的当前曲线（run 0）；旧历史 run ID 不由当前执行证明。仅有旧完成日志加无关追加、读取失败的相同未知值、同秒未变化日志均不能证明新执行；真实瞬态联合模式继续要求两侧独立执行证据。
- CST 2026 的同工程离散端口瞬态联合，还须匹配三维日志中的实际任务名、新的三维求解开始/完成记录、原生 `SUCCESS` 状态，以及每个三维端口带 `[cosim <task>]` 标识的电压/电流时域曲线。曲线必须覆盖任务时长；未能校准的外部工程或端口形式继续返回未验证。run 0 始终是保存工程的当前别名，审计摘要和导出的 CSV 用于保留本次数据，不能当作不可变历史编号。

详细签名、规格和验收门槛见 `docs/superpowers/specs/2026-10-19-design-studio-cosimulation-design.md`。本段是扩展协议；能力实测状态以 `docs/VALIDATION.md` 为准。

状态：`0.1.0` 首发接口，见 `docs/VALIDATION.md` 的离线验证边界。此文件是 TPC/em-enclosure 实现领域适配器的接口来源；变更接口时必须同步调整兼容性说明和验证记录。

## 依赖和模块导入

- 通用包名：`cst-automation`；Python 包名：`cst_solver`、`tpc_service`、`cst_mcp`、`cst_automation`。
- 核心导入：`from cst_solver import setup, Result`；数据分析：`from cst_automation.curves import contiguous_bands, find_resonances`；Touchstone 分组文本：`from cst_automation.s2p import read_s2p_groups`。
- TPC/腔体依赖 `cst-automation>=0.1,<1`。本地联调可以配置 editable path dependency；不得把机器绝对路径写进发行元数据。
- 导入 `cst_solver`、`tpc_service`、`cst_mcp` 或 `cst_automation` 不启动 CST，不修改 `sys.path`，不加载 CST DLL。第一次真实 CST 调用由 `cst_solver.environment` 发现/加载本机 CST 安装库。CST 的 `cst` 模块仅随 CST Studio Suite 提供，不从 PyPI 安装。
- Optional extra `mcp` 要求 Python 3.10+，并依赖 `mcp>=1.29,<2`；当前 `cst_mcp` 适配 MCP Python SDK 1.x API。
- 依赖方向：TPC/em-enclosure → 本包 → CST Studio Suite（仅真实 CST 操作）。本包不得 import `mesh_grid`、`topo_modeler`、`topo_templates`、`em_enclosure` 或 `tpc_toolkit`。

## Runtime guard API

```python
from cst_solver.guards import get_guard_state, get_guard_mode, set_guard_mode
```

`cst_solver.guards` 是守卫状态/发现的稳定模块入口；`cst_solver` 包根也继续导出这些名字。`get_guard_state(owner)` 以宿主对象（通常是 `setup` 实例）隔离状态；传入 `None` 得到一次性状态。`set_guard_mode("off" | "warn" | "strict")` 设置进程级模式并返回旧模式。`GuardState`、`GuardFinding`、`CstGuardError`、`assert_gain_mode`、`require_project_file` 等公开符号见该模块的 `__all__`。`cst_solver._guards` 是实现模块，新的领域适配器应导入 `cst_solver.guards` 或包根，避免依赖下划线模块。

TPC 当前源码仍有 `cst_solver._guards` 导入；相同函数已由稳定公开模块转出。将 TPC 调用点迁至 `cst_solver.guards` 属于 TPC 仓库的后续适配，本轮不改动源 TPC。

## 曲线与 S 参数 API

### `cst_automation.curves`

```python
contiguous_bands(
    freqs: Sequence[float], values: Sequence[float], *,
    threshold_db: float, criterion: str = "below",
    max_gap_ghz: Optional[float] = None,
) -> List[Dict[str, Any]]

find_resonances(
    freqs: Sequence[float], values: Sequence[float], *,
    kind: str = "min", min_prominence_db: float = 0.0,
    band: Optional[Tuple[float, float]] = None,
) -> List[Dict[str, Any]]

match_resonances(first, second, *, tolerance_ghz=None, name='') -> Dict[str, Any]
resonance_criterion(first, second, *, limit_ghz=1.0, tolerance_ghz=None,
                    name='') -> Dict[str, Any]
```

保持来源 `tpc_toolkit.curves` 的实际签名和返回结构（实现迁移后由 introspection 与兼容测试固化）：频率单位 GHz；输入曲线为 dB；连续合格点按采样索引分段，可选最大频率间隔；谐振用三点局部极值及 prominence，不插值。输入长度不一致、非法 criterion/kind 等继续抛 `ValueError`。唯一规则实现位于本模块；MCP 适配可包装错误，但不得重写判据。

### `cst_automation.s2p`

```python
read_s2p_groups(filepath) -> tuple[numpy.ndarray, numpy.ndarray]
filter_by_frequency(data, freq_range, atol=1e-6)
filter_parameters_by_condition(data, param_strings, freq_range, threshold,
                               comparison='less', mode='any')
find_param_indices(original_params, selected_params)
```

逐字迁移原函数（以签名检查为准），保持分组文本解析、NumPy 数组返回、标签与异常行为。Touchstone 的其他格式/复数网络矩阵不在此函数承诺范围内。

## 对话持久会话（显式启用，2026-10-27）

`tpc_service.sessions.SessionManager(root, *, backend="cst")` 是本机文件队列管理器。
每会话一个独立常驻 worker 进程，所有 SDK 调用在该进程主线程执行；管理器客户端
可退出，任务和 DE 保留。root 必须是显式已授权绝对目录，不使用 cwd 推导会话位置。
backend 可显式为 fake（测试边界，不证明 CST 行为）。

方法：`ensure(binding, request_id)` 分配绑定不启动 DE；`status(session_id, credential)`、
`submit(session_id, credential, request_id, operation, params=None, operation_id=None)`、
`job(session_id, credential, job_id)`、`resume(session_id, credential)`、
`close(session_id, credential, request_id)`。submit 返回持久 job 记录；同 request_id
同载荷返回原记录，不同载荷报 request_id_conflict。operation_id 标识阶段，阶段重复
提交复用既有任务而不执行第二次；变更载荷须使用新阶段 ID。

绑定首次分配的 `(binding, request_id)` 是恢复引用的一部分，重复 ensure 返回同一凭据；
不能在不同对话共享这两个值。凭据不写入公共任务和状态。没有宿主可信 thread ID
时仅保证会话路由，不能认证真实聊天身份。工作目录须是当前用户信任的本机目录，
不提供跨用户恶意进程隔离。文件队列不执行任意 Python 或 shell，只接受显式操作。

操作：`start`、`create_project`、`import_project`、`inspect`、`history`、`set_parameters`、
`solve`、`circuit`、`close`。写入工程要求显式 project_id；history 要求 stage_id、
name、vba、preview_digest（与实际 VBA SHA256 相符，调用前须完成人工预览审阅）。
该摘要证明输入对应关系，不冒充用户审批凭证。恢复不重新复制或重放未知副作用。
create_project 支持 MWS/DS；import 默认复制到本会话独立工程目录，不支持跨会话就地写入。
`circuit` 接受 kind 和原有 circuit handler params；借用同一 app，finally 不关闭 DE。
失败或进程丢失后的未知执行进入 needs_reconcile；未证实空闲的存活 DE 仅允许诊断。
`resume` 仅恢复 worker/精确连接；不会自动重放原 running 任务。关闭前已接收的队列
按序完成；新写入被拒绝，关闭失败保持 close_failed。客户端断线不关闭环境。

MCP 通过 `--enable-sessions --session-root ABSOLUTE_PATH` 显式注册：ensure_cst_session、
get_cst_session、submit_cst_session_operation、get_cst_session_job、resume_cst_session、
close_cst_session。每个调用显式传递 session_id/credential，不存在全局当前会话。
旧工具仍为临时模式，不得对持久会话工程混用。SDK 对象不进入队列/JSON。

原生常驻和 PID 重连测试使用空环境；未据此承诺几何或 solver 已通过。

人工核对入口：`reconcile(session_id, credential, review_note, project_digests, *,
confirm_idle=False, environment_identity=None, confirm_no_environment=False, abandon_projects=None)`。只在
needs_reconcile/close_failed 且无 running 任务时可用。调用前必须由用户核对现场；
提供全部工程当前 SHA256 和明确的空闲确认，保留原未知任务为 resolved，不将其
升级成 succeeded。DE 创建回执丢失时须人工给出完整进程身份，或明确确认无环境存活。
任何已被另一活动会话记录的 DE 身份都拒绝接管；环境身份赋值由根目录锁串行化。
首次工程未落盘时，可显式 abandon_projects 放弃不存在且未确认保存的工程意图，
不得因此删除已有文件。关闭意图独立存储，不能解除前驱未知状态的写入屏障。
恢复日志记录这是 human_reviewed，readback_verified/solver_verified 仍为 False。
MCP 显式注册 `reconcile_cst_session`，不得由 agent 无人核对时自动使用。

## `tpc_service` 生命周期与状态

`RunService(workdir, backend=None, *, clock=None, recover=True, autostart=True)` 创建运行服务。默认 backend 是惰性加载 CST 的 `CstBackend`；离线使用必须显式传入 `FakeBackend` 或自定义 backend。worker 单线程串行执行。服务重启时 queued/running 记录标记 interrupted，不自动重跑；排队任务可取消为 interrupted，运行中的 CST 不承诺可取消。`close_project` 只关闭服务拥有的会话。产物必须受限在服务 workdir 中。

```python
service.register_handler(
    kind: str,
    handler: DomainHandler,
    *,
    replace: bool = False,
) -> None

class DomainHandler(Protocol):
    def __call__(
        self,
        *,
        project: Mapping[str, Any],
        params: Mapping[str, Any],
        job: Mapping[str, Any],
        backend: Backend,
    ) -> Mapping[str, Any]: ...
```

`kind` 是 `RunService.submit` 已接受的操作之一：`build`、`solve`、`study`。handler 在调用 `submit` 前注册；它会在唯一 worker 线程同步执行，不能自行并行启动 CST、不能把 session 放进返回值/任务 JSON。`project`/`params`/`job` 是本次调用的只读快照；不得修改它们并假定改动会持久化。`backend` 提供通用 CST 操作能力，领域包可调用其公开方法，不应访问服务私有状态。handler 结果字段与 backend 一致：`ok`、`error`、`log`、`artifacts`、`run_identity`、`result_summary`；有项目保存/求解的操作必须返回 `saved: True` 才可成功。

- 重复注册默认抛 `ServiceError(code="domain_handler_exists")`；显式 `replace=True` 替换同 kind handler。handler 注册仅在当前 `RunService` 实例生命周期有效，不写入磁盘。
- 服务调用每个任务时先查对应领域 handler，再调用 backend 内置同名方法。通用 `CstBackend.build` 与 `study` 不内置领域实现；找不到 handler 返回 `domain_handler_missing`，details 含 `kind`、可操作提示和调用 `register_handler` 的说明。通用 `CstBackend.solve` 接受已有工程并调用 CST，不依赖拓扑结果读回器。
- 传入未知 kind 时由 `submit` 抛 `ServiceError(code="unknown_job_kind")`。
- handler 抛出的异常由服务捕获并记为 `backend_failed`，保留异常类型/文本；handler 可返回 `fail_result(...)` 表达可诊断业务错误。

### 服务稳定方法签名

```python
submit(kind, *, project_id=None, project_path=None, params=None,
       request_id=None, copy=True, overwrite=False, note="") -> dict
get(job_id) -> dict
list_jobs(*, status=None, kind=None) -> list[dict]
wait(job_id, timeout=None) -> dict
logs(job_id) -> list[str]
artifacts(job_id) -> list[dict]
result(job_id) -> dict
open_project(path, *, copy=True, overwrite=False, project_id=None,
             session=None, session_owned=False, note="") -> dict
projects() -> dict
close_project(project_id, *, save=True) -> dict
cancel(job_id) -> dict
shutdown(*, wait=True, timeout=None) -> None
describe() -> dict
```

工程可用 `project_id` 或 `project_path` 指定，提交返回 queued 记录。`wait` 返回当前终态/状态快照；超时返回仍在运行的记录，不等于任务失败。重复 `request_id` 返回既有任务，不重复执行。`get`/`result` 输出保留状态、错误、产物、执行身份和弹窗诊断。完整字段和错误码保持 `tpc_service` 代码文档与测试为准。

## Fake backend 与 handler 示例

```python
from tpc_service import RunService
from tpc_service.backends.fake import FakeBackend
from tpc_service.backends.base import ok_result

service = RunService("./work/offline", backend=FakeBackend())

def offline_build(*, project, params, job, backend):
    return ok_result(saved=True, log=[f"accepted {job['job_id']}"],
                     result_summary={"mode": "offline-example"})

service.register_handler("build", offline_build)
# 提交后由 FakeBackend 支持的异步服务生命周期处理任务。
```

此例只说明 handler 调用协议，不证明 CST 安装、几何读回或求解成功。真实领域 handler 必须用安装的 `cst-automation` API 并单独记录 offline、readback、solver 证据。

## `cst_mcp` 扩展入口

通用 MCP 包导出 `register_tool(name, definition, handler, *, replace=False)` 与 `dispatch(name, arguments=None)`。definition 为 MCP tool definition 字典；handler 接受 JSON arguments dict 并返回 `{'ok': True, ...}` / `{'ok': False, 'error': ...}` 结构。重复名字报结构化 `tool_exists`，未知工具返回 `unknown_tool`。领域包应在自己的可执行入口显式注册扩展，不允许 cst_mcp 自动 import TPC。

写操作需标注为 write tool 并通过 `RunService`；MCP adapter 本身不得直接发 CST VBA。stdio stdout 仅用于 MCP 协议帧，诊断写 stderr/产物。包不安装或改写用户 MCP 客户端配置。

## 兼容与版本策略

- 首个拆分版 `0.1.x` 保留 `cst_solver`、`tpc_service`、`cst_mcp` 导入名，以及源 `curves/s2p` 的函数行为。
- `0.x` 的跨包协议变更按次要版本明确记录；`1.x` 承诺稳定公共 API。新增/移除 handler kind、任务状态、错误码字段或工具扩展行为需更新此文档和测试。
- TPC 提供的 `tpc_toolkit.curves` 与 `.s2p` 延迟兼容入口由 TPC 维护，本仓库不分发旧 `tpc_toolkit`。
