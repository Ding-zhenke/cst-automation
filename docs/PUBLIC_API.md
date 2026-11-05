# cst-automation 与领域包的公共接口

## 2026-11-05：失败回执保留锁存监测证据与加载代码身份

worker 收尾在不覆盖主错误 code/message/原详情的前提下，将本任务 session_monitor.first_failure、final_snapshot、failure_latched 写入错误详情（有监测证据时），并在 job.completion_evidence 记录 prior_status、状态决策、原因、unknown/launch 与监测失败因素。首个监测失败即使最终 snapshot=clear 仍保留并阻止 returned_saved 放行；离线判定也读取回执内锁存证据。不以最后 clear 自动恢复、不改变监测严重性或重试未知写入，不回写旧 job。

job.worker_runtime 记录 worker PID、sys.executable/Python 版本、实现修订标记，以及实际加载的 worker 规则函数/已加载 operations.execute 的 code-object SHA256（marshal 版本另记）。不靠磁盘 HEAD/插件版本伪称旧 worker 已加载新代码；指纹为本机/Python 代码对象身份，不是跨机器通用发布签名。原始错误与完整几何/求解回执保留；监测快照不可用要明确记录，不能将证据缺失当 clear。

## 2026-11-05：几何验证的消息级别、已保存失败与只读审阅

validate_model 按原生 type 分级，记录 before/rebuild/合并消息摘要、rebuild_performed/rebuild_returned 及 dependency_validation=unknown。纯 INFO 不把正常返回的 Rebuild 判为异常，但非空 INFO/WARNING 仍 status=unverified；ERROR/未知或 Rebuild 异常为 error。消息正文不用于提升几何/依赖通过，外部源缺失不能因 INFO 或缓存存在自动通过。无消息的原 success 口径保留。

set_parameters/model_api/configure_sweep/3D history 的验证失败若有明确操作及验证返回、正常 Rebuild 返回和保存回执，worker 核对同工程/操作/任务身份与登记/磁盘摘要，且原 ready、无未知/弹窗/启动意图，保留 failed job、geometry_unverified/review_required 和 returned_saved，session 可 ready。不建立成功 checkpoint，不允许 depends_on 将该失败当通过；原 needs_reconcile、缺回执、Rebuild 异常、保存失败等继续围栏，不回写旧任务。

inspect 增加显式 native_readback=True/read_only_review=True/confirm_idle=True/expected_digest，用于该几何错误围栏的原生只读审阅。要求已登记保存文件/摘要相同、原环境身份存活、无其他运行/排队/未知任务/弹窗，且目标标签实际已打开。只借用既有 app 或精确 attach 原 PID，不调用 Runtime.environment/project 恢复、不 open/activate/rebuild/save/solve、不消费消息队列或修改会话状态；只执行既有受限 getters。目标不在打开列表就拒绝。inspect 成功仅表示查询返回，geometry_verified=False、idle_verified=False，fence 保留；默认 inspect 在围栏内仍只返回元数据。

## 2026-11-05：首次 create/import 与旧工程恢复检查分离

create_project/import_project 在复制检查之后、登记新 project 意图之前取得/恢复原环境，并刷新当前登记快照；新 project 不参加这一步针对旧工程的恢复审阅检查。随后仍在原生 open/new/save 之前持久登记 saved=False 意图，保留中断/未知写入围栏和路径占用。adopt_project 及原 restore_reviewed_projects 的缺失旧工程审阅/摘要校验不放宽，不添加跳过全部 unsaved 的例外。

已失败且已有目标文件/登记的 import 不自动重试、不覆盖或重新导入：由所属会话核对原任务阶段、文件/配套目录、输入与目标摘要、原 DE 空闲，按现有授权通过 reconcile API 采纳全部登记工程的真实磁盘基线（不是手改 human_reviewed）。保留原错误与 resolution 审计，再沿同一 project_id 做 inspect/受控后续操作；原 request-id 仍返回原回执。缺文件、未知 native open/save 或未审阅状态继续围栏，不能因更新代码自动清除。

## 2026-11-05：已关闭过程工程的显式退休

`close_project` 增加可选 `retire=True, expected_digest=<64位小写SHA256>, confirm_idle=True, review_note=<非空审阅说明>`。默认行为不变。显式退休只接受本会话 projects/<project_id> 内、已登记关闭/保存的 .cst 过程文件；登记摘要、请求摘要和磁盘一致，且 session ready、无未知任务/启动意图/已知弹窗、无其他 queued/running/needs_reconcile job、无目标缓存句柄。调用方确认正式交付和依赖不再使用该过程副本；API 不认证这条外部事实。

该分支在原 already_closed 返回之前处理，不调用 environment/project/save/close，不重开标签、不删文件，将同一记录从 projects 移至 retired_projects，保留原 lifetime、摘要及显式 retirement_review。回执 retired=True、already_closed=True、environment_closed=False、files_deleted=False，idle_asserted_by_caller=True/idle_verified=False。已退休的同摘要记录可幂等返回（文件后续删除不影响已有退休回执），不回写旧 job。外部正式路径、其他归属、未关闭/未保存、摘要变化和忙碌/未知状态拒绝；正常 working 关闭仍不自动退休，temporary 原规则保留。

## 2026-11-05：会话普通异常的受限诊断

worker 对非 ServiceError 仍返回 session_operation_failed，新增 details.diagnostics：exception_type/module、受限 message、OSError errno/winerror/filename/filename2、明确执行 stage、operation/job_id，以及每层最多 12 帧的文件/函数/行号和最多 3 层原因异常。不记录 locals、请求参数或源码正文；文本限制 4096 字符，明确截断/省略。阶段仅表示最后进入的代码边界，不证明其副作用完成或失败文件的 OS 根因。

ServiceError 原有结构与 returned_saved 放行规则保持；普通异常仍 needs_reconcile，不凭 PermissionError/磁盘未变/增加诊断自动重试、重放或提高验证等级。不回写旧 job。阶段覆盖工程恢复、History 提交、原生保存、摘要核对、登记落盘和 checkpoint 写入，供后续新回执定位。

## 2026-11-05：工程绑定的存储参数 ByRef 桥接

新增纯构建/解析契约 `cst_automation.run_parameter_bridge.prepare_run_parameter_query(project_path, result_id, *, receipt_root)` 与 `parse_run_parameter_receipt(payload, *, request)`；只接受固定正 Schematic ID，为每次请求生成独立 token/输出路径。VBA 在显式 schematic 上校验 GetProjectPathName("Project") 后调用文档所载 GetParameterCombination(resultID, names, values) 的 Variant ByRef；不猜 Python tuple/输出参数形式，不查 Current Run 0。

`cst_solver.circuit.native.read_project_run_parameters(project, result_id, *, expected_project_path, receipt_root, confirm_idle=False)` 仅在调用方明确 confirm_idle=True 且既有 project.filename 与登记路径一致时，执行一次固定生成的只读宏，核对回执 token、实际资源路径、ID、计数与有限参数值；不保存/关闭/求解/重连。circuit/build 新增显式 read_run_parameters（result_id、confirm_idle=True），审计输出仍限 service.workdir；沿既有 submit_cst_session_operation 提交；通用 circuit 服务无可信 borrowed_project host 标志时在 app_factory 前拒绝此操作，JSON 不能伪造该标志。 会话查询要求已有 app/缓存工程句柄、未关闭登记及存活原环境；不调用可能 attach/重开标签的 Runtime.project/environment 恢复路径。此为文档/离线契约验证，native_bridge_verified=False；confirm_idle 是调用方断言，不是库独立探测空闲。仅由所属会话在实际空闲后首次只读核验。

## 2026-11-05：Update 异常审计与后处理运行身份

`CircuitAPI.run_checked` 区分 update_call_state（not_called/calling/returned/raised）与 execution_returned（仅正常返回为 True），并保留 failure_stage、原始异常及磁盘/日志变化证据。Update 包装调用抛错返回 Python 不证明原生执行停止或 DE 空闲；保存策略为 deferred_until_idle，saved=False，未知写入围栏保留。异常路径不再误记为结果读取失败，不盲目保存、重跑或提高验证等级；所属会话确认空闲后独立保存，不改历史失败回执。

新增 SDK-free `cst_automation.result_identity.select_schematic_result_id(available_by_path, parameters_by_id, *, expected_parameters, requested_id=None, rtol=1e-10, atol=1e-12)`：目标曲线共同枚举的正 Schematic ID 必须和实际存储参数组合匹配。正 requested_id 只允许严格绑定本 ID，空/零别名只允许唯一匹配；拒绝缺参、非有限值、歧义和跨域，不按最大 ID、全局 last ID 或存在曲线推断当前轮。输入枚举与参数组合必须由调用方实际读取，此纯选择器不连接 CST、不验证数值或新鲜度。

`cst_solver.circuit.native.resolve_schematic_result_id(schematic, tree_paths, *, read_parameters, expected_parameters, requested_id=None, rtol=1e-10, atol=1e-12)` enumerates native target IDs and calls the explicitly verified stored-parameter reader. It does not guess the CST ByRef binding.

## 2026-11-04：电路叶任务已返回保存与未知写入分离

`CircuitAPI.run_checked` 新增 project、submitted、execution_returned、saved_digest 回执，分别记录提交意图、原生调用返回及保存后文件摘要；缺少新日志仍保持 unverified，不替代原生完成或数值验收。session 仅对 circuit/kind=solve/operation=run_task 的这一明确回执，核对同一 project_id/路径、登记摘要与当前磁盘；无弹窗失败、未知前序、启动意图且原状态 ready 时，失败 job 保留完整 outcome、execution_state=returned_saved 和 review_required，session 保持 ready。保存异常、缺回执/摘要或不一致、其他操作及已有 needs_reconcile 不自动放行；不回写历史 job，不自动 reconcile，不以 ready 自动继续依赖任务。

## 2026-11-04：正式工程的 circuit 路由

session circuit 使用同一登记 project_id/规范路径；外部正式工程还须具有匹配的 path_authorization（create/import/adopt）。只把这一文件的可信授权交给 `register_circuit_handlers(..., authorized_project_path=None)`，不接受请求参数伪造该授权。默认通用服务仍要求工程位于 workdir；所有 destination、模板源和输入文件仍按原 workdir 检查，不扩大到正式目录。
未更新的旧父日志不作为当前叶任务错误：无新日志时 completed=False、log_changed=False，历史错误单独保留；有曲线但无本轮日志仍 unverified，不用结果数量补执行证明。

## 2026-11-04：分级消息与已返回保存的求解回执

- RunContract 保留 JSON 可表达的原生消息对象；只按原生 type=INFO/WARNING/ERROR 分级，不靠正文关键词或解析历史 repr 升级证据。INFO 不单独导致失败；WARNING 保持 unverified/需审阅；ERROR 和未知类型保守 failed。messages_clean 表示完整读取且没有非 INFO 消息，queue_empty 另记真实空队列；原生完成、网格/数值和 validation_passed 不因 API 状态提升。
- `RunContract.run_and_record(..., read_prior_messages=None)` 先写审计意图以确认可用，再于提交前读取并立即持久化旧队列。`setup.run_checked(read_messages=True)` 同时使用前后读取；前读或前置记录落盘失败不提交。保留 prior_messages/state/summary/审阅标志，提交后消息不按文本相同去重；message_scope 为 post_boundary_queue 或 pending_queue_unbounded，均不宣称原生 Run ID 绑定。回溯旧 repr 记录不自动修改历史状态。
- session solve 仍将非 succeeded outcome 记为失败；若有明确执行返回回执、保存成功、登记摘要与当前磁盘一致、同工程/运行身份，且没有未知前序或弹窗失败，保留完整 outcome/save receipt，session 可保持 ready。ready 只代表会话可继续受控操作，不是警告、结果或物理验收通过。调用者须审阅失败 job，不得据 ready 自动宣称成功。缺回执、保存失败、摘要变化、未知执行或模态错误仍 needs_reconcile；已有 needs_reconcile 不自动解除。

## 2026-11-04：Qt glow 的结构识别先于正文预算

`list_dialogs` 对精确 `QtitanTitleBarGlowWindow` 增加读取前结构校验：空标题、可见/响应中、
同 PID 的 Qt QWindowIcon owner、相同且已知的进程创建时间、无原生子控件且无已知正文/按钮/进度。
匹配后保留快照，标为 decoration、blocking=False；不调用 UIA，不受共享正文预算耗尽影响。
`text_source=win32_glow_structure`、`content_read_status=not_applicable_decoration` 表明是结构证据，
`text_readable/text_complete` 保持 False，不伪造已读取正文。结构不完整或含矛盾证据仍按原路径读取，
失败保持 unknown/blocking；真正模态窗口仍独立报告。不自动关闭窗口或改变原 job/session 状态。

## 2026-11-03：SPICE 缓存身份核验（离线回归）

- `configure_nonlinear_model` 不再要求 SPICE `GetFile()` 与 `SetFile` 路径相等。输入保持兼容；请求源快照增加字节数及可解析的 `.SUBCKT` 端口顺序。只支持唯一、简单的子电路声明；复杂语法、编码及 include/lib 依赖闭包保持 unknown。
- `readback.spice_verification` 保留 requested_source_path、native_file_reference、project_path、block_name、resolution_base、resolved_cache_path、source/cache 快照及原始错误。相对引用仅按已绑定工程文件的父目录解析，不用 cwd；缓存归属只在当前工程资源目录 `Model/DS/Block/<block_name>/` 下确认，符号链接按实际目标检查。工程资源内的其他未校准布局（含无法绑定的 sibling/numeric block 目录）保持 unknown，资源外引用为归属不符。源路径直引单独标为 source_reference，不冒充缓存归属已验证。
- 内容按批准源 SHA-256 比较（即使路径相同也检查）；端口按批准子电路声明的名称和顺序比对，模型和显式方言独立核验。内容/模型/方言/端口/缓存归属的明确不一致进入 `circuit_build_partial`，失败 readback 保留各维度证据；缓存文件不可读或声明无法解析保持 unknown，`verification_complete=False`。原生 metadata/pins 查询异常仍按已有部分失败处理，不伪造完整核验表。未知不等于通过，整体 readback_verified、saved_reopen_verified 和 solver_verified 仍为 False。
- 顶层内容核验不证明依赖闭包、接线/极性或器件仿真语义；不调用 `SetCacheFiles`，不自动重导入、保存重开或求解。核验仅在调用方授权的稳定副本上读取源和原生返回的缓存文件。无新增 service/MCP 操作或隐式 SDK 加载。

## 2026-10-30：通用电路参数研究（新增，离线验证）

`CircuitAPI.run_parameter_study(spec)` 执行显式逐点序列；不是原生 Parameter Sweep 的别名。`spec` 包含 schema_version=1、name、安全名称的 parameters（scope=em/circuit、unit；可选 block/property）、points（values 完整有限数值映射）、task（name、mode=network、results=[{name,tree_path,run_id}]），可选 em（results=[{tree_path,run_id}]）。全计划预检后在当前保存工程中运行；EM 参数必须具有显式 EM 依赖，EM＋电路每点重算。仅支持同工程 self EM；无自动缓存复用或瞬态双向联合扩展。EM 放行要求指定原生数据文件指纹更新、原生 SUCCESS 和对应 EM 参数一致；通用目录/日志变化不作为替代证据。全局参数必须与原始结果元数据一致，缺失/冲突返回 unverified；block/property 别名使用属性 SI 读回，不要求出现在全局参数表。静态属性限制由 NativeAdapter 与 study 预检共享。执行入口要求显式当前 run_id=0，读取后立即固定到不可覆盖的历史快照；不接受历史编号作为新求解结果。全局参数的 unit 为调用者核对的原生单位声明，元件绑定的 unit 通过已有 API 转换并读回 SI 数值。

批次写入 `<project>/Result/DS/Studies/<name>/<batch_id>/study.json`，每点原始复数/单位/证据不可覆盖；汇总曲线写入 `Results\Studies\<name>\<batch_id>\<result>\<component>\<case_id>`。`StudyResult(batch_path)` 提供 list_cases(parameters=None)、read_curve(case_id,result_name)、compare(result_name,parameters=None,component='magnitude')、verify_project()。保存后原生读回独立于真正的关闭重开，reopen_verified 始终保持 False，待拥有会话的调用方完成重开。离线测试不证明实机运行；保存读回与真正的关闭重开分开报告。搬运时保留 .cst 及其同名结果目录，不承诺单个二进制封装全部 JSON/CSV/.sig。

服务增加 `study/run_parameter_study`（spec）；MCP 显式增加 `run_circuit_parameter_study`，复用唯一 worker。原参数序列与任务入口保持兼容。

## 2026-10-28：完整电磁张量材料

`setup.create_material_full_tensor(name, epsilon_tensor, mu_tensor, *, epsilon_imag=None, mu_imag=None, epsilon_axes=((1,0,0),(0,1,0)), mu_axes=((1,0,0),(0,1,0)), color=None, colour=None)` 对齐 CST 内置 Create Full Tensor Material 宏：电磁两组完整复数3×3矩阵、每组独立 TensorAlignment2。axes 为全局坐标下两条数值正交单位向量，第三轴 U×V；输入数学虚部，统一转换为 CST 负虚部。全输入先验证，提交单个历史块，不自动保存或求解。旧 create_material_tensor 保留签名并委托新接口，将标量 epsilon 展开为对角矩阵。原生适用范围仍为四面体通用频域。


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
- `validate_circuit_spec(spec, *, existing=None, defer_references=False)` 默认保持完整规格校验。
  `existing` 可传入当前 `CircuitAPI.inspect()` 快照，为分阶段新增连接、探针和任务解析
  已有元件/端口及连接占用；已有对象不会被加入返回的待创建规格。已有端点须有可读且
  可连接的实际引脚，不接受猜测索引或将已占用引脚重新分配到新网。`defer_references=True`
  仅作访问 CST 前的格式检查，不认证引用存在；`CircuitAPI.apply` 和服务 configure 必须
  随后使用当前工程快照完整校验，才允许写入。已有名称冲突仍报错，不重建或删除对象。
- 电路 `inspect/list_pins` 的 `pin_name` 使用实际连接端口名，`display_pin_name`
  单独保留带标签的界面名称；通过当前原生端口名称/标签匹配 `pin_index` 与
  `port_index`，不假定两种索引一致，不猜测拆分标签。没有可靠匹配时保留不可连接。
  既有网络中的原生 `Externalport` 类型按 `ExternalPort` 识别，端点占用仍完整检查。
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
- 正数原生 run_id 也可能是同参数重算时复用/覆盖的参数状态编号。显式 ID 仅用于
  选择当前数据，固定某次执行须另存完整复数结果、原生日志、参数及工程/结果摘要；
  `result_conventions().run_id_semantics` 明确保留这一边界，不以正 ID 替代内容存证。

详细签名、规格和验收门槛见 `docs/superpowers/specs/2026-10-19-design-studio-cosimulation-design.md`。本段是扩展协议；能力实测状态以 `docs/VALIDATION.md` 为准。

状态：`0.1.0` 首发接口，见 `docs/VALIDATION.md` 的离线验证边界。此文件是 TPC/em-enclosure 实现领域适配器的接口来源；变更接口时必须同步调整兼容性说明和验证记录。

## 依赖和模块导入

- 通用包名：`cst-automation`；Python 包名：`cst_solver`、`tpc_service`、`cst_mcp`、`cst_automation`。
- 核心导入：`from cst_solver import setup, Result`；数据分析：`from cst_automation.curves import contiguous_bands, find_resonances`；Touchstone 分组文本：`from cst_automation.s2p import read_s2p_groups`。
- TPC/腔体依赖 `cst-automation>=0.1,<1`。本地联调可以配置 editable path dependency；不得把机器绝对路径写进发行元数据。
- 导入 `cst_solver`、`tpc_service`、`cst_mcp` 或 `cst_automation` 不启动 CST，不修改 `sys.path`，不加载 CST DLL。第一次真实 CST 调用由 `cst_solver.environment` 发现/加载本机 CST 安装库。CST 的 `cst` 模块仅随 CST Studio Suite 提供，不从 PyPI 安装。
- Optional extra `mcp` 要求 Python 3.10+，并依赖 `mcp>=1.29,<2`；当前 `cst_mcp` 适配 MCP Python SDK 1.x API。
- 依赖方向：TPC/em-enclosure → 本包 → CST Studio Suite（仅真实 CST 操作）。本包不得 import `mesh_grid`、`topo_modeler`、`topo_templates`、`em_enclosure` 或 `tpc_toolkit`。

## 环境发现与诊断约定

发行包不携带开发机安装路径。未配置时自动发现常见安装目录；显式参数、环境变量、用户 JSON 或兼容的 `config.py` 仍按原有优先级覆盖发现结果。显式配置无效时报告错误，不静默回退到其他安装。

`python -m cst_solver doctor [--json] [--probe]` 始终输出 JSON，`--json` 是显式格式选项。`diagnose_environment()` 保留原有字段；默认离线检查若发现配置的 SDK 目录不存在、没有可发现的 SDK 或已知接口 ABI 不匹配，返回 `status="unavailable"` 并在 `errors` 中给出原因，CLI 退出码为 1。其余未经导入的状态仍为 `not_probed`，退出码 0 只表示离线检查未发现阻断项。`probe=True` 才尝试导入接口；`importable` 不证明许可、工程读回或求解可用。

## Runtime guard API

### 消息观察契约修复（2026-11-02）

`RunContract.after_submit(record, *, messages=None, error=None,
messages_state='not_read', message_source='caller')` 要求直接调用者显式声明消息观察状态。
`run_and_record(submit, *, read_messages=None, note='', message_source='callback')`
自动记录 reader 的调用/迭代状态；setup.run_checked 使用来源 sdk_pending_queue。

新增 messages_state=not_read/read/read_failed、messages_read_attempted、messages_read、
message_source、messages_read_error。messages_clean 是 bool|None：完整读取时为空/非空
对应 True/False，未读或失败为 None。默认/显式空 messages 不构成已读证据；
直接 after_submit 的 read 状态须同时提供 messages。reader 的部分迭代结果保留，读取失败为
read_failed；None 等非可迭代返回按失败报告，不补成空成功。
未读/读取失败时原 succeeded 降为 unverified（messages_not_read/messages_unreadable），
已有 failed 保持 failed。messages_read_error 的旧 record 字段仍接受并优先判读取失败。

warnings_scope=audit；native_warnings_state=unknown、native_warnings=None，
native_solver_status=unknown（当前没有原生状态 reader）。消息队列读空不证明日志无警告。
mesh_convergence/validation_passed 仍与运行契约状态独立，不由未读消息或原生返回推断。

CstBackend 在成功及失败的 result_summary.run_contract 中保留完整运行记录，失败 error.details
亦保留该记录；服务状态/落盘和现有 MCP 查询原样传播，不增加隐式日志读取、求解或工具注册。
这是修复旧的误报成功行为；依赖 messages_clean 恒为 bool 的消费者需处理 None。

### Offline repair additions (2026-11-02)

`cst_solver.native` provides `vba_capabilities(project)`,
`execute_vba(project, code, *, target, timeout=None)`,
`circuit_probe_code(name, pin, reference=None, *, direction_inwards=True)` and
`new_net_code(component_ports)`. Targets are explicitly `model3d` or `schematic`;
no trial execution/fallback after native failure. Builders return VBA, not execution
or readback evidence. Net code uses an empty name, retains the generated name in
`GeneratedNetName`, applies topology and checks each pin's net name.

`cst_solver.host` provides `diagnose_host_session()`, `process_identity(pid)` and
`open_host_session(filename=None, *, pid=None, expected_creation_time=None)`.
The checked session entry refuses inaccessible/unknown desktops; attaching requires
PID plus creation time. It never retries or falls back to creating another DE.
Desktop accessibility does not prove IPC availability or machine idleness.
Legacy `setup` remains available; callers requiring preflight use this checked entry.

Dialog snapshots add process/owner creation identity and classification; raw
decoration snapshots remain in `list_dialogs` with `blocking=False`.
`acknowledge_known_error(snapshot, *, expected_creation_time, button)` requires
complete exact title/body and identity, rechecks them before sending a standard
Win32 button click, and returns `readback_status='required'`; it never clears a
monitor failure or claims recovery. Qt buttons without a supported click path
remain actionable diagnostics.
The initial acknowledgement policy recognizes only exact `History Error` titles
and OK/确定 buttons. Unknown titles are reported, not acknowledged.
Service errors `cst_dialog_monitor_failed` and `cst_dialog_scope_unknown` distinguish
failed observation and unconfirmed ownership from `cst_step_timeout`.

`cst_solver.convergence.mesh_convergence_report(samples, *, target,
expected_frequencies, required_passes=1, max_passes=None, computation_completed=None,
warnings=())` evaluates explicit per-frequency, per-pass Delta S observations.
It preserves residuals and warnings without interpreting them as equivalent to
Delta S. Missing frequency/pass data stays unknown. It does not read native
results or configure refinement. Existing run contracts add
`mesh_convergence='unknown'` and `validation_passed=False`: solver completion
does not certify mesh convergence. No documented explicit CONTINUE selector has
been found; do not substitute ForceRecalculateOldSamples or quiet mode.

```python
from cst_solver.guards import get_guard_state, get_guard_mode, set_guard_mode
```

`cst_solver.guards` 是守卫状态/发现的稳定模块入口；`cst_solver` 包根也继续导出这些名字。`get_guard_state(owner)` 以宿主对象（通常是 `setup` 实例）隔离状态；传入 `None` 得到一次性状态。`set_guard_mode("off" | "warn" | "strict")` 设置进程级模式并返回旧模式。`GuardState`、`GuardFinding`、`CstGuardError`、`assert_gain_mode`、`require_project_file` 等公开符号见该模块的 `__all__`。`cst_solver._guards` 是实现模块，新的领域适配器应导入 `cst_solver.guards` 或包根，避免依赖下划线模块。

TPC 当前源码仍有 `cst_solver._guards` 导入；相同函数已由稳定公开模块转出。将 TPC 调用点迁至 `cst_solver.guards` 属于 TPC 仓库的后续适配，本轮不改动源 TPC。

## 曲线与 S 参数 API

### 指定缺失样点的离线计划

`cst_solver.sampling.plan_missing_samples(requested_frequencies, *, frequency_unit,
available_frequencies=None, context_verified=False)` 为仅补算指定缺失正频率生成纯数据计划，
不连接 CST、不生成/执行宏、不删除结果、不修改自适应或求解器。所有频率使用同一明确单位；
去重按精确数值，不用宽容差合并相邻点。计划推荐 force_recalculate_old_samples=False。
仅当 available 非 None 且调用方确认缓存身份有效、配置为单点且无额外自动/monitor/adaptation
采样（context_verified=True）时，给出条件性的 expected_new_frequencies；否则为 None。
available=[] 表示明确无已存点，None 表示未知。该计划不认证缓存或保证原生实际点集/顺序。

`assess_sample_execution(plan, observed_frequencies, *, log_complete, aborted)` 只核对同一次运行、
同单位的日志观测频点；不解析二进制/原生日志、不归属残差、不推断 direct accuracy。
返回频点 mismatch/incomplete/matched/unknown 及独立的 aborted 状态；即便点集匹配，
accuracy_status=not_assessed、validation_passed=False。无预期点集或日志不完整不能判匹配。
native abort 保留为 aborted；不能因频点不符把另一频率的端口残差归到请求频率。

### `cst_solver.Result`：联合枚举与自适应 Pass 曲线

```python
enumerate_result_paths(*, modeler=None) -> dict
read_adaptive_s_parameter(tree_path, *, run_id, frequency_unit=None) -> dict
read_adaptive_s_parameters(*, run_id, modeler=None, frequency_unit=None) -> dict
```

`modeler` 只能由调用方显式传入已授权、与结果工程对应的 Model3D 对象；仅调用其
`get_tree_items()`。不创建/连接/关闭设计环境，不从 setup 或全局对象寻找会话。
默认仅枚举离线 results。枚举返回 `items=[{path, sources}]`（来源为 results/modeler，
精确路径去重，保留来源顺序）、`sources` 状态、`errors` 和 `complete`；读取失败不等于空树。
本接口不验证调用方 modeler 与结果工程的身份对应关系，该核对由调用方负责。

单条读取仅接受完整 `1D Results\Adaptive Meshing\f=...\S-Parameters\S...` 路径，
要求 xlabel 为 Pass、轮次为严格递增正整数，复数 S 数据长度匹配且有限。
返回 `path`、`sources=['caller']`、显式 `run_id`、可用时的 `native_run_id`、
`axis='mesh_pass'`、原始 `xlabel`、独立数组 `passes`/`s_complex`、`parameter`、
`adaptation_frequency`（raw/value/unit/source/unit_source）和 `normalization`。
频率原始标记来自路径；不能解析时 value=None，路径未带单位且调用方未给单位时 unit=None。
不推断工程单位、不转换频率或重归一化。`normalization` 保留
`get_ref_imp_data()` 返回的原生参考阻抗数据及来源、错误；缺失为 unknown，
`wave_definition='unknown'`、`renormalized=False`，不声称完整波归一化约定已被验证。
单条路径、run 或轴/数据错误抛异常，不回退最新 run；显式 run_id=0 仍是原生当前结果别名，
此时保留 run_id=0 和可能不同的 native_run_id；非零 run 与原生 run 不一致时拒绝读取。

批量接口联合枚举后只读取自适应 S 路径，替换每条 sources 为实际枚举来源。
返回 `curves`、`enumeration`、逐路径 `errors`、`complete` 及
`matrix_completeness='not_evaluated'`。没有候选项时 status=not_found，
枚举或读取失败时 status=partial/failed，全部已发现曲线可读时 status=ok；
ok/complete 不证明端口、频率或矩阵齐全。归一化元数据缺失保留在曲线中，不丢弃复数数据。
不做轮次插值、Delta S 排名或原生收敛验收。

普通 `list_s_parameters()` 仅匹配主频率树 `1D Results\S-Parameters\S...`，
不能把 Adaptive Meshing 的 Pass 曲线名称混入普通频率曲线发现、批量读取或导出。
原有通用 `read_1D` 仍按原始轴返回数据；它不将 Pass 曲线认证为频率曲线。

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

FakeBackend 的 `solve` 结果保留请求的 `run_id`（默认 0），用于验证身份字段的传递；`run_token` 仍带 `fake-` 前缀，产物仍为合成数据。

## `cst_mcp` 扩展入口

通用 MCP 包导出 `register_tool(name, definition, handler, *, replace=False)` 与 `dispatch(name, arguments=None)`。definition 为 MCP tool definition 字典；handler 接受 JSON arguments dict 并返回 `{'ok': True, ...}` / `{'ok': False, 'error': ...}` 结构。重复名字报结构化 `tool_exists`，未知工具返回 `unknown_tool`。领域包应在自己的可执行入口显式注册扩展，不允许 cst_mcp 自动 import TPC。

写操作需标注为 write tool 并通过 `RunService`；MCP adapter 本身不得直接发 CST VBA。stdio stdout 仅用于 MCP 协议帧，诊断写 stderr/产物。包不安装或改写用户 MCP 客户端配置。

## 兼容与版本策略

- 首个拆分版 `0.1.x` 保留 `cst_solver`、`tpc_service`、`cst_mcp` 导入名，以及源 `curves/s2p` 的函数行为。
- `0.x` 的跨包协议变更按次要版本明确记录；`1.x` 承诺稳定公共 API。新增/移除 handler kind、任务状态、错误码字段或工具扩展行为需更新此文档和测试。
- TPC 提供的 `tpc_toolkit.curves` 与 `.s2p` 延迟兼容入口由 TPC 维护，本仓库不分发旧 `tpc_toolkit`。


## Session native inspection without history

Session `inspect` accepts opt-in `native_readback: true`, with optional bounded
`parameter_names`, `solid_names`, and `sample_points` (id, solid, xyz `point`).
Omitted name lists enumerate the current model (at most 10000 entries per list).
Parameters (value and expression), solid material assignments, volumes and point
tests use native queries on the owning worker, without history, rebuild or save.
Volumes and coordinates use the project's geometry units. Query failures remain
explicit in `native_readback.errors` and set `readback_verified=false`; successful
queries certify only these reads, never geometry acceptance or solver success.
Fake sessions return `native_executed=false`, never native verification. Unsupported
inspection options, including the previously documented but unimplemented
`captures`, are rejected before queueing; image export remains a separate API.

### Project reuse and tab lifetime

`create_project` / `import_project` accept `lifetime="working"` (default) or
`"temporary"`. Reusing an existing project ID fails before queueing; importing
the same source again requires a nonempty `copy_reason` (independent topology,
reference or an explicitly needed relocation check). Queued intents participate
in this check. A source matching a registered working path is also a duplicate.
Ordinary parameter/solver/material changes and scan corners reuse the original
project ID. A different filename alone does not establish a different topology.

New session operation `close_project(project_id)` saves and closes only the
registered tab, retaining its file, digest, record, worker and DE. Its receipt
reports `tab_closed`, `saved` and `environment_closed=false`. Repeating it on a
closed tab does not reopen it. Later explicit operations can reopen that same
saved path; worker recovery skips intentionally closed tabs. Errors do not
discard handles or mark a failed close successful. Temporary checks must submit
this operation on completion; it is separate from closing the whole session.
The MCP session-operation enum explicitly includes this operation.
Native close is confirmed by listing open paths. Closed temporary projects move
from `projects` to `retired_projects`, retaining their path and saved digest as
audit records; reconciliation no longer requires those temporary files. Their
project IDs cannot be reused, and repeated close is idempotent. No file is deleted
by this operation. Working projects remain registered and can be reopened.

`setup.add_sweep_parameter_arbitrary_points(seq_name, param_name, points)` accepts
a nonempty bounded list of finite numbers and emits official
`AddParameter_ArbitraryPoints`; it only configures and never starts a solve.
`setup.configure_discrete_sweep(sequence_name, parameters, replace_all=False)`
validates all axes before one history submission. `parameters` maps names to
point lists. Explicit `replace_all=True` deletes old sequences before defining
the requested sweep. Session `configure_sweep` carries these three fields plus
`project_id` and stable `stage_id`; retries deduplicate by stage. No solve is
started. The operation is explicitly registered in the MCP operation enum.


## 2026-10-28：周期稳态射击法配置（仅离线验证）

- `CircuitAPI.configure_steady_state_task(task_name, settings, *, create=False)` 将明确的
  transient 任务配置为 `cst - steady state`，不保存、不调用 Update、不改变源、连接、
  积分设置或单位。`create=True` 只创建不存在的名称。它是 transient shooting，
  不表示支持 Circuit Envelope 或泵浦 HB 小信号线性化。
- `settings` 仅含 `automatic_period`（布尔）、`period`（正的 value/unit 时间数量）和
  可选 `tolerance`（有限实数，0 < tolerance < 1，拒绝布尔）。提供 period 时默认手动，
  否则默认自动检测；自动检测不允许同时提供 period，手动检测必须提供 period。
  省略 tolerance 时保留原生已有容差。手动周期按目标任务当前生效的时间单位换算，
  已有局部单位优先，不修改全局单位；新任务采用全局时间单位并校验创建后读回。
- 返回原生属性与单位读回、请求的 SI 周期及未验证字段。配置读回不证明激励具有共同
  周期、射击法收敛、实际积分步长或性能提速。端口周期波形、宽带时域宏模型、被动性、
  延迟及谱提取须在实际工程中独立核验。先完成普通瞬态/源设置再调用此接口；后续
  configure_transient_task 会按其显式模式重新选择普通或联合瞬态求解器。
- 服务显式注册 `build / configure_steady_state_task`，MCP 增加
  `configure_circuit_steady_state_task`，参数 `task_name/settings/create`。沿用串行 worker、
  保存、部分失败审计；非法输入必须在打开 SDK 前拒绝。未新增运行模式或改变运行证据。


## 2026-10-28: Session parameter descriptions

`set_parameters` accepts optional `expressions: {name: description}`. Keys must be a subset of `values`; values are UTF-8 strings. The worker calls existing `app.para(name, value, expression=description)`, preserving formulas in `values`. Fake backend stores descriptions separately; neither path certifies native readback.


## 2026-10-28: Typed session modeling API

`model_api` takes explicit project_id, stage_id, calls (method/args/kwargs) and a SHA256 preview_digest of canonical JSON calls (sort_keys=True, ensure_ascii=False). Only the static whitelist in sessions/model_api.py is callable; all signatures are bound before the first mutation. No scripts, eval, dynamic imports, solver run, file open/close or arbitrary attributes. Methods execute on the original session-owned app. Native stages rebuild and save through the usual checkpoint. Fake stages only record calls. This routing does not itself certify geometry or results.

Added setup.new_curve(name), set_wcs_basis(origin, normal, u_vector), activate_global_wcs(), configure_fem_solver(accuracy='1e-6', mesh_adaption=True). They submit focused history through the owning API; no solve. ExtrudeCurve now preserves the exact requested name; parameter sweep helpers omit unsupported Reset.


## Explicit schematic macro domain in persistent sessions

The existing `history` operation accepts `domain="schematic"` to execute a reviewed, bounded VBA statement body through the owned project schematic `execute_vba_code`. The default domain remains `model3d` and uses 3D add-to-history. Schematic execution is journaled and saved, but is not added to the 3D replay history and does not rebuild unrelated 3D geometry. Stage identifiers, SHA256 preview binding, project ownership and failure/recovery rules remain mandatory. It does not certify solver or source equivalence. No active-window routing or fallback between domains is permitted.


`reload_project` is a persistent-session operation for explicitly approved baseline recovery. It requires project_id and expected_digest matching the human-reviewed last_resolution and current saved file. It discards only that owned project tab without saving its unsaved state, reopens the same file in the same DE, and resets that project handle. It does not copy, rebuild or run a solver.

## Native linear, logarithmic and discrete parameter sweeps

`setup.add_sweep_parameter_samples(seq_name, param_name, lower_bound, upper_bound,
num_steps, logarithmic=False)` now exposes CST's native logarithmic flag. The
existing five-argument call remains linear. `num_steps` is the number of samples,
including endpoints, not the number of intervals. Bounds are finite numbers with
`lower_bound < upper_bound`; logarithmic bounds must both be positive. Sample
counts are integers in [2, 10000]. Configuration never invokes Start.

`setup.configure_sweep(sequence_name, parameters, replace_all=False)` accepts a
mapping of parameter names to either numeric point lists or range descriptors
`{"mode": "linear" | "logarithmic", "start": number, "stop": number, "samples": int}`.
All axes are checked before submitting one native history entry. It emits
`AddParameter_Samples` for ranges, retaining their native GUI sampling mode;
point lists emit `AddParameter_ArbitraryPoints`. Axes in the same sequence form
the Cartesian product. `configure_discrete_sweep` retains its point-list-only
contract. Session `configure_sweep` accepts the same mixed mapping without
changing its operation name, stage deduplication, or configuration-only scope.

The session `model_api` route also accepts the already implemented basic-shape
methods `create_brick`, `cylinder`, `create_cylinder`, `create_sphere`,
`create_cone`, and `create_torus`, plus the configuration-only sweep methods.
This extends explicit routing; it does not enable arbitrary Python or solving.

### Sweep configuration bounds and combination semantics

Mixed and discrete configurations accept at most 100 axes and 10000 samples per
axis, and at most 1000000 Cartesian cases per sequence. Sequence names cannot
contain control characters or double quotes. A native sequence evaluates all
combinations; simultaneous/zipped axes are not supported by this contract.
Independent sequences are separate experiments, not another Cartesian axis.
Validation completes before any DeleteAllSequences or AddSequence command.
The legacy low-level `add_sweep_parameter_samples` additionally accepts finite
decimal/scientific numeric strings for bounds; arbitrary expressions remain
unsupported. Mixed `configure_sweep` bounds stay numeric and reject strings.

## Typed frequency-domain sampling and tetrahedral mesh configuration

`setup.configure_fd_frequency(settings)` accepts a sparse mapping:
`sampling_intervals` is a list of `{start, stop, spacing, samples}` with optional
boolean `adaptation` (default False) and spacing
`automatic|linear|logarithmic|single` and `samples=None` only for automatic;
`adaptation_frequencies` is a list of positive single-frequency adaptation
points. Optional `output_samples` (integer >=2), `output_spacing`
(`automatic|linear|logarithmic|log_linear`), `sweep_error` (0,1],
`sweep_minimum_samples`, `sweep_error_checks` (positive integers), and
`stop_sweep_if_converged` (boolean) control broadband sampling independently.
Sample intervals append to existing ones; this sparse operation does not clear
inherited intervals. Explicit `replace_intervals=True` resets sample intervals
before adding the supplied rows; it requires at least one interval/adaptation
point. Inspect existing settings before choosing append or replacement.
Frequencies use the current project frequency unit. `output_spacing` controls
the shared adaptive-sweep/result-data frequency-axis mode in CST; it is not an
independent output-only setting. An automatic interval starting at zero does
not establish an actual DC solve; native omission/remapping is reported.
Automatic-interval adaptation is supported when explicitly requested; selection
depends on electrical size and expected mesh cost, not a universal ban. Large
problems normally keep automatic adaptation off and use a few explicit points.

`setup.configure_tetrahedral_mesh(settings)` accepts sparse positive
`steps_per_wavelength`, `minimum_steps`, boolean `material_refinement`,
`local_solids=[{solid: "component:name", max_step: positive number}]`, and
`adaptation={enabled, min_passes, max_passes, max_delta_s, delta_s_checks,
refinement_percentage}`. Adaptation values are optional; passes/checks are
positive integers, max_delta_s is in (0,1], refinement_percentage in (0,100].
Sizes use current project geometry units. Keys outside these schemas fail
before history submission. These calls use documented tetrahedral commands,
not hexahedral LinesPerWavelength or speculative MeshShapes region commands.

Both APIs validate the entire request before submitting history. They do not
reset, choose a solver, rebuild, save or solve. Return values record requested
settings/history submission with readback_verified and solver_verified False.
No cross-case mesh/solution reuse switch is promised. Session `model_api`
explicitly registers both configuration methods; MCP uses that existing route.

Tetrahedral global `steps_per_wavelength`, `minimum_steps`, and material refinement
currently submit legacy `Mesh` setters: the receipt reports
`global_controls_backend="legacy_mesh"` and an explicit warning. This does not
establish effectiveness on a modern active HF Tet mesh-settings group.
`active_mesh_settings_group=None` records the missing native group readback;
local-only/adaptation-only calls report global_controls_backend=None. Local
solid limits use `Solid.SetMeshStepwidthTet`; adaptation uses FDSolver and
MeshAdaption3D. Those paths are separate. Global/local MeshSettings keys vary
by mesh type, group and item type; do not infer a new mesh size from a history
setter or an unchanged initial cell count. Native effective settings and mesh
generation remain separate acceptance evidence.

### Frequency-domain CPU parallelization

`setup.configure_fd_parallelization(settings)` configures CPU parallelization on
the current `FDSolver`, independently of transient `Solver` and Design Studio HB.
Its nonempty sparse mapping accepts `enabled` (boolean), `threads` (positive
integer CPU thread count) and `cpu_devices` (positive integer CPU socket count).
Omitted fields are preserved; specifying a thread limit alone does not enable
parallelization. No thread count or hardware topology is inferred. It uses the
documented `UseParallelization`, `MaxCPUs`, `MaximumNumberOfCPUDevices` setters;
there is no reset, solver selection, GPU change, rebuild, save or solve.
Session `model_api` explicitly routes/preflights the method and returns its
configuration receipt. Settings readback is unsupported: actual_threads is None,
cpu_parallelization_verified/readback_verified/solver_verified stay False. Check
actual threads in the native run log. Native history failure preserves partial
evidence via `FDomainConfigurationError`, with no automatic retry.

### Modeling audit corrections and explicit session coverage

`boundary` now sends each xmin/xmax, ymin/ymax and zmin/zmax value to the
matching native face (previously reversed). `create_hexagonal_prism` preserves
the requested curve group. `create_torus` keeps the documented centerline/tube
major/minor radii and converts them to native OuterRadius=major+minor and
InnerRadius=major-minor, including parameter expressions. Existing scripts
that compensated for the former incorrect mapping must remove that workaround.

Session `model_api` additionally registers basic prisms/wires, curve creation
and extrusion, boolean intersection/insertion, transforms, picks, WCS changes,
custom/tensor materials, explicit waveguide/discrete/lumped ports and monitors.
The maintained whitelist remains in `tpc_service/sessions/model_api.py`; SDK
lifecycle, arbitrary property setters, filesystem import/export and solving
remain separate operations. Signatures are checked for the full batch; new
frequency, tetrahedral-mesh and sweep settings also get pure payload preflight
before any call executes. `stage_id` is the default operation identity for
`model_api`, so a new request ID cannot accidentally replay the same stage.

`setup.delete_solid(name, component="component1")` and
`setup.delete_curve_item(name, curve="curve1")` delete only the named object,
using documented Solid.Delete and Curve.DeleteCurveItem commands. Names are
nonempty local names without colon, control characters or quotes; group names
are separate. Neither API clears the model or starts solving. Both are explicit
reviewed-geometry session methods. `model_api.configuration_receipts` retains
the typed frequency/mesh return receipts; their unverified flags remain False.
`scale(name,factor,center=None,component="component1")` emits the requested
native ScaleFactor for a numeric/symbolic scalar or three-component vector;
the prior implementation omitted the factor entirely. Input is validated before
history submission. Offline command tests do not certify native geometry.
`mirror(...,object="Port")` uses native port names without component prefixes
and AutoDestination=False. Integer port IDs normalize to "Port N"; shape
mirroring retains its component-qualified names. This corrects the old shape
rules incorrectly applied to ports.
Executing session `model_api` batches reject `log_flag` values other than the
integer 1 before any batch mutation. Code-generation-only log_flag=0 belongs
outside this route and cannot produce a successful modeled-stage receipt.
## HB post-processing configuration evidence

`cst_solver.circuit.native.configure_hb_postprocessing_chain(schematic,
parent_task, hb_task, post_task, *, create=False)` configures an existing native
Parameter Sweep and Spectral Lines child, optionally creates a new `template`
child, enables all three and moves HB immediately before Post at the end of
the parent's task list. Both child names must be full paths directly under
the parent. Creation refuses name conflicts; update refuses absent/wrong-type
tasks. This does not bind any result template, save, rebuild or solve.
`inspect_hb_postprocessing_chain(...)` reads native types, enabled flags,
task folders and the actual Results-tree sibling order. Task-chain readback
is distinct from result-template registration and saved/reopened evidence.

`cst_automation.result_templates.inspect_embedded_python_result_template(
project_resources, *, metadata_path, expected_settings, expected_sha256=None)`
checks one explicit existing local-copy module, metadata settings and its
Summary.rpp registration entry. It never executes code or edits files.
`resource_integrity_verified` is **not** native binding verification. Generic
task folders do not identify the actual template-resource folder, and this
API does not invent a suffix or copy an unrelated project's Summary.rpp.

`app.circuit.register_python_result_template(parent_task, hb_task, post_task,
template_source, *, result_name, template_name, group, result_type, settings,
eval_type="single_run", create=False, conflict="error", expected_registration_sha256=None)` imports
one embedded Python registration into a dedicated Post task using the
versioned CST 2026.1 resource format. Only the explicitly tested native build
is supported; this is a resource-format adapter, not an undocumented VBA
AddTemplate command. Only the observed `single_run` format is accepted. Device
parameters, task/probe names, metrics and outputs belong to caller settings.
`inspect_python_result_registration(folder)` returns the descriptor and a
digest covering Summary.rpp, metadata and source; replacing a registration
requires conflict="replace" and that digest. Multiple registrations in the
same Post task are refused rather than truncated. Source is statically
checked and never imported, defined or evaluated by registration.

For the observed v11 single-module M0D layout, inspection also accepts the
native output-name list written after evaluation: a nonnegative count,
exactly that many unique names belonging to the registration, and the known
terminal flag. `native_output_count/native_output_names` report this index only;
they do not certify successful evaluation or result correctness. Unknown
expanded formats and multiple registration modules remain refused. The full
current Summary bytes participate in registration_sha256, so evaluation makes
an older digest stale. Inspect again and provide the new complete digest before
replacement. Replacement retains old resource bytes in its audit backup and
writes a fresh registration descriptor; it does not execute the template or
recompute HB, nor does it certify a subsequent native callback.
RPP `P/EP10` flags do not independently establish eval_type: the known-valid
reference using these flags declares single_run. Inspection returns eval_type
None with status not_independently_decoded and preserves raw flags. The
request declaration is reported separately as requested_eval_type; explicit
incompatible literals in source define() are refused without executing it.
No all_runs encoding or callback behavior is certified.

Registration configures/enables HB->Post, explicitly saves, closes and
reopens the owned project in the same DE. To establish archive persistence,
the task resource folder is moved to an audit backup outside the companion
directory after closing. Native reopening must reconstruct all three files
from the saved .cst; their contents, settings, registration descriptor and
task chain are compared. Backups and an audit receipt remain beside the
project in `.cst_automation_template_audits`. This is an explicit native
archive round-trip, not a file-existence test. On failure preserve partial
evidence; do not retry automatically or claim success. Returned
registration_persistence_verified certifies that round-trip only.

The DS iterator returns empty outside its active processing context, including
for the known-valid control. Thus native_template_enumeration_verified and
template_execution_verified remain False; registration does not certify
runtime calculation. It never calls Update, Start, EvaluateResultTemplates,
an EM/DC/HB solver, a mesh generator or a scan. Session build operation
`register_postprocessing_template` explicitly routes this facade on the
owning app and refreshes its project handle after reopening.


## Explicit session working paths and existing formal projects

`SessionManager.submit(..., operation='create_project'|'import_project', params=...)`
accepts optional absolute `working_path` (`.cst`) together with
`authorize_working_path=true`. Authorization covers only that exact path in
that durable request; no global directory allowlist is changed. Omitting both
retains the existing session-local `projects/<project_id>/model.cst` default.
Create/import reject existing destinations and paired results directories.
Import copies its explicit source and never saves over that source.

The explicitly registered `adopt_project` operation requires `project_id`,
`working_path`, `authorize_working_path=true`, `expected_digest` (SHA-256 of
the saved file), and a nonempty `review_note`. It opens that existing baseline
in place without copying or saving it during adoption. Later normal writes
operate on that authorized formal path. The durable owner, project ID, path,
digest and adoption review remain in the same session recovery records.
Destination claims, including queued jobs, are exclusive among sessions in
the same session root; different roots and external processes are not an
OS-wide ownership registry. Resume uses the original reference/project ID,
never a new adopt/import request. Offline tests do not certify native opening,
saving, recovery, or solving.
Failed project-operation journals retain their destination claim until
explicit reconciliation resolves the receipt, including failures before
the native-open result could be registered as a project. A state-only change
does not release an uncertain claim.
