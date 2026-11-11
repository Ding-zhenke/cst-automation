# 验证记录

## 2026-11-11：owned-worker 原生交接与 mixed-order 生效（所属会话回报）

- 所属工程会话报告完成 0.3.46 owned 路径验收：独立小工程由实际 worker 创建 DE，诚实声明 owned 后交接至新 worker，原 DE/标签/参数及三点 synthetic/not-EM 存储曲线逐项一致。随后目标工程同样完成 owned-worker 交接，原 DE 保持，全部登记标签、完整参数及当时结果树前后相同。
- 目标工程旧矩阵仍为 unqualified；结果树一致不等于矩阵数值逐项复核，也不提升原失败结果。全程未强杀、未使用 Computer Use、无 DE create/reopen fallback。该证据限定于本次环境和已审阅对象，不推出所有 SDK/worker 版本兼容性。
- Direct + tet_order=Second + mixed_order=True 已实际进入原生计算；在同为 159634 初始 cells 的对照下，DOF 从固定二阶的 1111562 降至 351425，支持数值离散配置生效。回报时任务尚在 pass 3；不认证最终残差、Delta-S、完整频段、EM/HB 或物理性能，不据该快照声称任务现在仍处于同一阶段。
- 交接后另行通过 API 关闭六个已完成参考标签，保留正式文件，所属会话报告释放约 7 GB。标签清理与 mixed-order 作用分开，不能将这部分内存变化归因于阶次设置，也没有据 DOF 变化推断最终峰值内存。
- 原始审计留在所属会话私有 work 目录的 native_handoff_owned_validation 与 R02/EM_mixed2/handoff；不发布身份、凭证或工程文件。维护端本次仅根据所属会话回报更新记录，未独立读取私有回执或接触正在运行的任务。

## 探索性线性 SP 接口（仅离线）

新增探索性网络准备和 SP 配置、求解门槛，未访问原生会话。任务单位按官方 GetUnit
增加读回代码；采样点数和端口阻抗缺少已验收的独立原生读回，配置和求解入口当前均在写入前拒绝；原 EM
失败保持失败，本路线不放行 HB。已有外部端口也被拒绝，以免隐含新增 SP 端口。
本次未执行或验证原生任务创建、网络替换、求解或保留 DE 交接。

## 2026-11-11：HF Tet 阶次设置与显式 owned-worker 交接（离线）

- 核对本机 CST 2026 FDSolver 官方帮助 OrderTet/MixedOrderTet：First/Second/Third，混合阶次以指定阶次为上限；新增 typed tet_order/mixed_order，保持其他设置不变。启用 mixed 必须同请求明确上限，严格布尔和枚举校验先于整批写入。
- 新增 43 项回归，覆盖稀疏命令、非法值、MCP、纯设置无 Rebuild/solve、提交/执行能力门槛、旧 worker 的位置/关键词/混合批次拒绝，以及 owned 确认互斥、幂等身份和 DE 丢失不启动替代进程。完整离线 **1963 passed、2 deselected、9 warnings**（53.07 s），日志 work/tetorder-full.log；两项 skill 格式检查通过，独立源码复审无阻断项。
- 新 worker 能力 hf-tet-order-controls-v1。原生阶次读回、实际 DOF/内存降低、残差/Delta-S 收敛均未在维护端验收；混合或降低阶次改变离散方式，不能据配置成功或用量下降放行 EM/HB。
- owned-worker 使用单独 ownership/确认/退出风险接受，不能虚填 borrowed。独立创建控制进程退出后 DE 保留的观察，不等于完整 owned-worker 交接通过；须所属会话先在实际 worker 创建的独立小工程验收。原 exact-DE/标签/基线复查及无 fallback 边界保持。
- 维护端未连接、停止、接管或修改实际工程/DE/worker。所属会话报告的有界 Iterative 失败和正常 API 停止不在本项中提升为求解验收。

## 2026-11-11：独立小工程原生交接与恢复验收（所属会话回报）

- 所属工程会话报告已完成 0.3.44 原生验收；维护端本次仅接收回报并更新文档，未独立打开私有回执或访问 CST。原始审计保存在所属会话私有 work 目录的 native_handoff_validation/{verified.json,recovery_receipt.json,latest_handoff.json}，不随公共插件发布。
- 在确认失败启动器完整进程树无存活后，显式 recover 保留失败尝试并旋转 token，随后 finish 从 stop_requested、starting、release_requested 推进至 complete；覆盖客户端中断后的接续。
- 独立小工程原 DE 身份、原标签、测试参数值和三点存储曲线前后逐项一致，新 worker 已加载 HF controls 能力。曲线明确标为 synthetic/not-EM；没有执行电磁计算，不认证物理结果、网格收敛、真实 EM/HB 结果或所有 SDK/旧 worker 版本兼容性。
- 没有强杀、create/reopen fallback 或 Computer Use。之后 close_project 回执 saved/tab_closed/retired 均为 true，environment_closed=false；该清理与交接完成分开记录。
- 主工程未执行保留活 DE 交接：所属会话确认其旧 DE/worker 已退出，按原 reference 普通恢复。主线正在运行的求解不计入本项验收，也未被维护端访问或干预。

## 2026-11-11：Windows venv worker 身份交接修复

- 所属工程会话报告：独立小工程旧 worker 正常退出且原 DE/标签/参数/存储曲线保留，新 worker 被启动器身份比较拒绝。维护端通过源码定位 Popen 启动器与实际 Python 子进程身份混用；未访问该工程或 DE。
- 新增 15 项测试：nonce/父子身份/解释器/重放拒绝，冻结恢复的令牌、活进程、worker 锁、已登记 worker、原生变化拒绝，以及实际 Windows venv Python 子进程登记。真实子进程测试断言未加载 CST SDK，不等于原生交接验收。
- 修复后完整离线回归 1917 passed、2 deselected、9 warnings（44.29 s）。独立源码复审无阻断项，技能格式检查通过。原生小工程交接的后半段仍须所属会话继续验收。
- 整合远端 ADS 2025 兼容更新后的最终完整回归为 **1920 passed、2 deselected、9 warnings**（43.17 s），日志 `work/launcher-merged.log`；发布插件 0.3.44，打包测试通过。
- recover_native_worker_handoff 仅恢复尚未登记实际 worker 的已消费启动，保存旧尝试并旋转令牌，不启动进程。原生状态必须不变；失败启动器整棵进程树已退出仍需现场审阅，不从启动器死亡或空日志自动推断。

## 2026-11-11：保留原 DE 的显式 worker 交接（离线）

- 新增 32 项离线用例；完整回归 **1902 passed、2 deselected、9 warnings**（50.32 s），日志 `work/handoff-full-final.log`。会话 skill 格式检查通过。没有启用实机或界面测试。
- 显式试验入口覆盖冻结、旧 worker 协作退出、精确 DE/标签/完整参数与保存摘要核对、一次性启动令牌、新 worker SDK 线程复查，以及不超过 2 秒的令牌绑定最终观测。失败保持冻结，普通 resume/reconcile/upgrade 不得绕过。
- 独立代码复审提出的陈旧放行、并发启动、失败态绕过及结构化错误丢失问题已修复；复审未发现剩余代码阻塞项。原参数→EM→HB 提交和执行拒绝测试同属本次完整回归。
- 此版本不证明实际旧 worker 退出后编译 SDK 保留 DE，也不证明已部署 worker 的兼容性、原理图空闲或完整非参数内存/磁盘等价。仍须所属会话明确批准并先做独立小工程验收；普通升级继续拒绝活 DE。
- 本次未访问或操作实际 CST 工程、原 worker、DE 或求解；安装插件不会触发交接，也不会热更新运行中的 worker。

## 2026-11-11：HF Tet 奇异边细化和几何投影（离线）

- 官方 MeshAdaption3D 文档核对 SingularEdgeRefinement 0..3、Automatic refinement 前提和 SnapToGeometry bool；新增受限 typed 设置，沿用显式注册的 service/MCP model_api 路径。未增加猜测的现代 MeshSettings 键或 legacy 质量优化替代。
- 新增 33 项回归（含现有纯设置路径的两个参数化用例）；定向回归通过，整合远端更新后完整离线回归 1870 项通过、2 项实机/界面测试排除、9 项既有警告。覆盖命令顺序、稀疏配置、非法类型/范围、整批预检、旧 worker 拦截、MCP 传输和无 Rebuild/solve。
- 需要实际 worker 宣告 hf-tet-adaptation-controls-v1；新字段对旧活 worker 在排队前拒绝。未重启、接管或操作正在运行的 CST、工程或 worker。
- 命令实际生效、参数原生读回、结果保留、保存重开、网格改善和收敛仍未实机验收。奇异边细化可能突破普通增长限制，不等于低质量优化迭代预算。
- 活 DE 协作交接仍被拒绝，未实现/宣称安全热升级；所需冻结、原身份保留、无创建/重开 fallback 和独立实机验收路径见 guides/hf_tet_adaptation_controls.md。

## 2026-11-11：警告 EM 的外部探索性证据

- 新增独立 `qualify_exploratory_em`：只读核对返回保存、WARNING、原生直接采样/各激励残差、正 Run ID 全矩阵和绑定代次；失败和 WARNING 保留，mesh 为 unknown，不设置正式 EM/HB 放行回执。
- 离线替身验证拒绝异常、未返回、监测故障、代次变化、缺频点/端口、旧 worker 和不完整日志。实际存档 Model.log 的只读解析不代表真实 SDK 矩阵资格或器件验收。该入口不输出 ADS 文件，原生执行与保存数据读取集成仍未实机验证。

## 2026-11-11：结果兼容性弹窗分类与重复消息观测（离线）

- 新增 5 项回归，先复现缺失字段/未知分类，再修复；完整离线回归 1821 项通过、2 项实机/界面测试排除、9 项既有警告。首次受限运行出现失败且未完成，未计为验收；在允许测试子进程的环境完整重跑通过。诊断 skill 格式检查通过。
- 已知结果不兼容标题使用专用诊断代码，仍阻塞并锁存原失败；没有实现自动缓存选择或清除围栏。消息读取不再宣称必然消费队列，重复快照不去重、不提高几何验收等级。
- 所属工程对话反馈 saved-baseline 实机采纳成功、随后 EM 启动；本维护任务未独立读取工程或控制器，因此不据转述补写完整实机认证。自动缓存策略和原生消息时段绑定仍未完成。
- 本轮没有访问 CST 工程、worker 或任何实际窗口，没有重启、取消或重复求解。

## 2026-11-11：已审阅参数保存基线的接续规则

- 明确区分工作流自动检查与 `depends_on`：前者检查绑定代次、磁盘摘要和执行时原生值；后者只接受 succeeded。已返回保存但因监测失败的参数任务，只有按原回执、定向 reconcile 与实际原生读回审阅后才可接续，原失败审计不改判。
- 本次为文档规则澄清，未修改会话执行代码、启动求解或提升真实几何/求解验证等级。旧 worker 的实际能力以所属会话状态及代码为准。

## 2026-11-11：ready 状态外部保存基线接受（离线）

- 新增 47 项专项测试；仅含暂存改动的隔离发布副本完整离线回归 1791 项通过、2 项实机/界面测试排除、9 项既有警告。会话 skill 格式校验通过。合并远端并发恢复/升级修复后，最终集成副本完整回归 1816 项通过、2 项排除、9 项既有警告；集成复审通过。
- `accept_saved_baseline` 增加独立、显式的基线采纳入口；旧登记摘要、当前磁盘摘要、审阅文档摘要、原 session/DE/原已开 tab、完整参数表达式与数值、块类型和指定属性均须一致。
- 同一原子状态更新登记摘要、追加审计并清除旧 EM/HB/拟合放行证据，增加输入代数。旧任务、错误和 resolution 保留；不通过制造失败、改历史任务成功状态或放宽普通写入门槛恢复。
- 不创建/重启 worker，不打开/关闭/保存/重建/求解 CST。需已有兼容 worker；只读不匹配保留 ready。同步弹窗检查失败、背景监控失败、落盘前后异常均保留围栏。
- 独立复审发现并修复同步弹窗异常在背景监控尚未捕获时可能被当作普通读回拒绝的问题，复审无剩余阻塞项。
- 未对实际工程调用此入口，未重启原 worker 或读取其控制器。EM idle getter、全参数/块与属性读回、原 tab 借用及整个新入口仍待所属工程实机验收。电路空闲和标签无未保存编辑仍由调用方真实确认，不认证完整磁盘/内存几何等价。

## 2026-11-11：几何只读审阅的当前弹窗检查（离线）

- 历史 `runtime_diagnostics` 与本次窗口状态分开；在精确 DE 身份与目标 PID 上同步检查当前弹窗。离线替身覆盖旧锁存、本轮阻塞、检查异常及原围栏不变，本轮独立监测仍锁存真实失败。
- 本轮未操作或重启真实会话。新逻辑的真实 CST 弹窗读取与几何 getter 集成尚未实机验证；旧 worker 不会因源码更新自动加载新逻辑。

## 2026-11-11：会话恢复与模型频段（离线）

- 定向 reconcile 仅处理显式列出的任务，其他失败及阻塞回执保持原状；缺少不确定任务时拒绝解除围栏。既有接管审阅仅在同一路径、摘要和无未知状态时用于重开缺失标签。
- `set_frequency_range` 的独立 settings-only 路径使用已有 `Solver.FrequencyRange` history，跳过库发起的完整 Rebuild 并保存；旧 worker 需要 `model-band-no-rebuild-v1`。这是离线测试结果，不证明原生设置读回、历史结果保留或保存重开。
- 本轮未操作用户工程、原会话或运行任何 CST 求解；实际结果历史和模型频段须在所属会话、授权条件下独立检查。
- 旧 worker 不消费协作停止请求，不能以一次空闲检查证明随后强停无竞态。新版协作升级及并发冻结只做 fake 测试，旧 worker 拒绝，活原生 DE 明确拒绝；不能由插件更新推断旧 worker 已加载新能力。

## 2026-11-10：DS 任务截止调查

- 查阅本机 CST 2026.1 帮助：`-c -u` 是 DS 结果更新，未见其选定单任务或独立进程保证；`-b` 仅用于指定的非 DS 模块。现有 `Model3D.abort_solver` 的历史实机案例属于 3D，不能推出 DS 任务可取消。
- Windows Job 的进程归属与停止条件及尚需隔离验收见 [DS 截止调查](guides/ds_bounded_stop.md)。本轮无真实任务中止或批处理进程隔离验收；未接触 H040 和其他会话。

## 2026-11-10：独立 DS 网络瞬态入口（部分验证）

- 新增所属会话 `run_network_transient`：未绑定受保护工作流时，原生检查目标为网络瞬态且无子任务，拒绝未经支持的 MOR 强制复用和取消参数；已有参数/EM/HB 保护不变。无原生取消和 MOR 命中证据时不得以此入口执行要求这些能力的任务。
- 在独立空 DS 工程通过 API 创建瞬态任务，原生读回 simulator=cst、tmax 和 sampling method；入口通过目标任务检查后对无效结果路径拒绝，回执确认 submitted=false，未启动求解。该失败回执让独立会话进入 needs_reconcile，保留原现场；随后已将结果路径校验前移至提交阶段。没有操作 H040 工程。
- 离线检查覆盖请求保护、原生类型与子任务、拒绝未支持选项；尚未实测有结果的瞬态求解、MOR 命中、120 秒原生取消及停止回读、引用迁移或保存重开。

## 2026-11-10：实际低频拟合与内嵌 HB 交接（离线）

- 隔离发布副本完整回归 1733 项通过，2 项实机/界面测试排除，9 项既有警告；随后补上的临时块创建即时接线保护，在最终发布副本 44 项专项测试中全部通过。对应 skill 格式校验通过。
- 新增强制会话操作 `prepare_hb_embedded_network`，真实正 Run ID 全矩阵比对、逐端口最终网格实际 LF 记录及残差、临时原生 MOR、独立 DC 数值核对、原位 SetFile、保存后有效内嵌载荷和可观测拓扑比较。
- 保留 EM generation，清除旧数值报告；HB 前自动复查来源、全部产物、有效载荷和原生源/负载断言。旧 worker 拒绝新操作而不重启；部分失败保持现场围栏。
- 独立复审发现并修复“保存频轴含插值点却当作实际 LF 求解”的缺口，复审无剩余阻塞项。
- 参考既有归档代码和内嵌文件读回证据；本轮未操作任何实际 CST 工程、worker 或求解。新组合操作的原生 getter、MOR、保存后内嵌文件及整体执行仍待所属工程实机验收。DC 为拟合近似，非独立零频 EM。
- 原生参考阻抗是已审阅输入，尚无独立 getter 认证；拓扑比较只覆盖适配器可读字段，未宣称完整任务属性/探针绑定。接口当前要求英文自适应网格/宽带日志阶段边界。

## 2026-11-10：独立保存 EM 资格与受控网络交接（离线）

- 新增 45 项专项测试；仅含本次暂存内容的隔离发布副本完整离线回归 1690 项通过、2 项实机/界面测试排除、9 项既有警告。
- 新增 `qualify_saved_em`：不取得工程控制器、不保存、不求解、不清除现场围栏；正常空闲审阅后，依据原失败回执、代数/摘要、原生同轮时间窗、收敛/残差记录、正 Run ID 的完整复数矩阵和参数建立独立资格。原失败异常不改写；下游重读固定 Run ID 检查覆盖漂移。
- 只读归档日志的解析核对通过，未对实际工程提交资格、读取 SDK 结果或确认现场空闲。原生结果 SDK/完整资格仍待所属工程空闲后的实机验收；未认证独立 DC。
- 新增 `fit_em_network/update_hb_network`：同工程内置 EM 块拟合、同顺序的单文件非缓存 Touchstone 更新，保留 EM generation、源/负载核验及数值报告门槛。未知原生 getter、旧 worker、旧导出、外部来源、错序或旧矩阵均拒绝。
- **现有内嵌 Touchstone、临时低频文件拟合、显式矩阵重排和有效嵌入数据读回仍未打通**。没有将有限的文件块接口声称覆盖该工程链，没有关闭缓存、修改端口或重跑工程。
- 独立审查提出的来源绑定、端口顺序、覆盖旧导出、残差身份和资格漂移问题已修复，复审无剩余阻塞项（在上述有限接口范围内）。

## 2026-11-10：按编号替换波导端口（离线）

- 隔离发布副本完整离线回归 1645 项通过、2 项实机/界面测试排除、9 项既有警告。
- 24 项专项通过，包含非法请求不启动 worker、不排队，整批原类型核对失败不写入历史、部分失败不重试、非目标端口改变被拒绝，以及重建后复查。独立审查指出的逐项预检问题已改为整批先查，复审无剩余阻塞项。
- 依据本机官方 Port 对象帮助封装精确编号删除与同编号创建；读取原生编号、类型和模式数，缺少查询能力时在删除前拒绝。仅支持数值轴对齐截面；不接受裸 history 或任意删除。会话要求 `port-replacement-readback-v1`。
- 未访问工程、CST、DE 或正在运行的 worker。实际 Python 到原生 Port getter 绑定及端口替换仍待实机验收；离线替身验证不代表原生执行。截面、边界兼容、模式场/阻抗、保留端口电气可用性与矩阵归一化分别验收。

## 2026-11-09：四面体网格设置避免全量重建（离线）

- 相关专项 60 项通过；隔离发布副本完整离线回归 1621 项通过、2 项实机/界面测试排除、9 项既有警告。独立代码审查无剩余必修项。
- 新增测试先复现原路由调用 Rebuild、旧 worker 未拦截的三个失败，再修复纯网格设置批次。仅配置网格及受支持 FD 设置时检查消息、保存、不全量重建；混合几何仍走原路径。所需 worker 能力为 `mesh-settings-no-rebuild-v1`。
- 只读核对本机官方 `Online Help/mergedProjects/VBA_3D/special_vbamesh/special_vbamesho.htm`：Delaunay 和 Advancing Front 的旧质量/过渡命令不同，现代 MeshSettings 的全局/局部键也不同。没有找到足以验证活跃 HF Tet 组质量 setter 的依据，未猜测封装、未切换网格器。
- 未操作七管工程或 worker、未生成网格或求解；原生结果保留与活跃组效果未验证。MOR/DC、Touchstone 更新、受控 HB 激励仍是独立未完成接口。

## 2026-11-09：F 求解器线性设置与无全量重建路径（离线）

- 17 项专项测试通过；隔离发布副本完整离线回归 1618 项通过、2 项实机/界面测试排除、9 项既有警告。独立代码审查无剩余必修项。
- 新增稀疏 `configure_fd_linear_solver`，枚举 Auto/Iterative/Direct、布尔迭代限制与正整数上限在提交前校验；记录原生命令，不 Reset、不自行求解，不把上限截断描述为保证回退 Direct。
- 会话中仅含线性、频率或并行配置的 model_api 批次调用 `validate_model(rebuild=False)` 后保存；保留消息检查和 EM 证据失效，不认证几何，也不清除已有脏几何状态。混合几何批次保留原完整重建行为。
- 活跃旧 worker 缺少 `solver-settings-no-rebuild-v1` 时在排队和启动前拒绝。未操作当前七管工程、未重启 worker、未执行短对照或全频求解；实际命令生效、结果保留与运行收益仍需所属工程空闲后验证。

## 2026-11-09：参数 → EM → HB 强制门槛（离线）

- 专项 40 项通过；只含本次暂存内容的隔离发布副本完整离线回归 1601 项通过、2 项实机/界面测试排除、9 项既有端口朝向警告。隔离副本首次运行因临时目录父目录缺失产生初始化错误，补齐目录后完整重跑通过，不计失败运行作验收。
- 新增不可省略的会话规格绑定、提交前检查、执行前复查、输入代数与 EM 证据失效、原生 getter 断言和数值报告比较。CLI/MCP 共用入口；已标记工程的旧临时服务在构造 app 前拒绝。
- 测试以隔离工程和模拟 app 验证拒绝请求不启动 worker、不取得 CST 工程、原生不匹配不调用求解器；也覆盖合法链、失败写入、文件变化、旧 worker 与规格修订。旧底层执行单元测试明确测试内部 dispatch，新测试另测不可跳过的公开入口。
- 未连接或修改运行中的 CST、会话、DE；未重启 worker。原生 getter 在实际目标版本上的可用性及整条实机链未验收。插件更新不会热加载旧 worker，旧进程的新受保护请求因能力缺失而拒绝。
- 报告为可信数值分析输入，门槛重算比较与摘要，不独立认证生成报告的分析算法。技能完整阅读要求继续保留；此功能不声称能证明助手读完全文。

## 2026-11-09：禁止技能截断阅读（指令与分发）

- 0.3.25 在全部十二个技能入口前部、skills/README.md 与 AGENTS.md 明确：入口全文及本操作必需引用章节未读齐，不执行依赖写入/求解；工具输出截断要连续补齐，上下文压缩后只有摘要要恢复全文。不以文件摘要或“已读”勾选代替阅读。
- 十二个技能格式校验及实际插件打包回归通过。本轮仅改指令、文档及插件版本，未更改运行库；不重复宣称上一轮完整测试是本轮重新执行。
- 这些检查验证文件格式和分发内容，不证明代理会完整阅读或宿主会阻断违规工具调用。当前插件没有宿主读取拦截器；工作流检查器也未成为 service/MCP 的强制提交门槛。真实行为验收仍缺。

## 2026-11-09：跨轮次工程交接与插件一致性（离线）

- 完整检查来源对话、技能读取命令与当前实现；修订参数覆盖、阻抗语义、网格成本、模板输入和跨轮次要求恢复，详见 [流程可靠性复查](validation/workflow-reliability-audit.md)。已存在的参数 update/结果保留修复不重复计为本轮成果。
- 新增纯标准库只读清单检查脚本：缺证据、过期输入、工程身份变更、证据文件覆盖/丢失、节点缺失、实际值不匹配均不通过；不连接 CST，不替代原生读回，也未接入 service/MCP 的强制求解拦截层。
- 针对性 17 项通过；完整离线回归 1561 项通过、2 项排除、9 项既有端口朝向警告。首次受限运行出现失败并挂起，未视为通过；确认仅为本轮测试进程后停止，在具有进程查询权限的环境完整重跑得到上述结果。七个修改的 skill 通过格式检查（UTF-8 模式）。
- 修复插件遗漏 skills/README.md，统一源清单版本为 0.3.24；本地安装后逐文件核对构建包。未操作来源工程或重启 CST/worker，未验证活跃对话重新读取或实机交接执行效果。

## 2026-11-07：持久会话队列索引与热路径测量（离线）

- Windows 隔离目录合成 1168 份历史回执，每份约 64 KiB。原路径新提交读 2337 份、约 154 MB，取队列读 1169 份、约 77 MB。索引建立后两步各只读 1 份新回执，单次样本分别由约 0.97 s 降至 0.12 s、0.37 s 降至 0.006 s。首次构建约 0.25 s。数据大小和本机时延只代表该合成测量。
- 原 JSON 持续作为队列与回执依据。索引写入中断、无索引旧回执、阶段重试、活动状态及原检查点恢复通过离线验证。worker 启动时完整核对原回执，热路径仅枚举文件名和读取必要回执。完整 status 的返回范围不变。
- 会话和相关打包检查 219 项通过。未操作运行中的 CST、DE 或 worker。实际队列时延和两组正 3D Run ID 保留由所属会话在空闲后接续核验。

## 2026-11-06：EM 逐点参数更新与结果历史

- 原工程会话报告：在同一所属工程以写参、`app.update()`、`run_checked`、保存的顺序，先后运行两组不同几何参数；四条 S 参数复数叶均有两个正 3D Run ID，参数组合读回分别匹配。此证据来自原工程会话，并非本次独立重跑；尚未验证保存关闭重开后两组结果均可读取。
- CST 2026 本机 Application VBA 帮助说明 `Rebuild` 删除全部结果，`RebuildOnParametricChange` 保留适合跨参数变化的结果；SDK `full_history_rebuild()` 的内部实现不可见，不将两者声称等价。改用已由原工程观察的 SDK `app.update()` 路径，后置验证不再执行 `Rebuild`；其他几何历史操作仍按既有完整重建处理。
- 离线回归验证会话路由、异常和消息处理、求解阶段不二次重建。当前改动本身尚未在原生会话执行；原工程需在安全加载版本后，验证两参数、四条复数 S 叶、正 Run ID 和对应参数，并在保存关闭重开后重复读取。不对全部结果类型的保留作保证。

## 2026-11-06：Windows 会话回执替换的短暂占用（离线）

- 隔离目录复现：普通 Python 只读句柄打开目标 JSON 时，原 `os.replace` 返回 WinError 5，旧 JSON 保持完整，关闭句柄后替换成功。会话有可与替换交叠的读取路径；来源事故的实际占用进程未确认。
- WinError 5/32 仅重试原子替换，沿用同一份已经刷盘的临时文件及原有调用方锁。持续失败时原异常继续上报，不改旧记录或回执恢复判据。Windows 实际占用回归验证保存调用一次、同源重试、持续拒绝保留原回执及其他错误即时失败。
- 211 项会话相关离线检查通过。来源工程的求解、读回和恢复由所属会话负责，本轮未访问其现场或刷新 worker。

## 2026-11-06：Schematic History 部分写入的定向恢复（离线）

- 区分完整原生 VBA 错误响应和连接/调用回执未知。新回执在截断宏回显前记录已返回错误，继续保留写入围栏；旧回执仅在完整格式和当前围栏匹配时可进入定向恢复。
- `recover_schematic_history` 限定同一失败 job、所属 DE、已打开项目及登记/磁盘保存摘要。只读查询参数和块。显式授权回退时用单标签 `Project.close()` 丢弃未保存修改，核对摘要及相邻标签后在原 DE 重开保存点。失败、监测异常和无回执继续留围栏；原失败记录保留，回退不自动 reconcile。
- 同步远端基线后的 89 项相关离线检查通过，含长回执、跨会话、未知写入、摘要变化和关闭失败。来源两个 job 只读查询时均为 `resolved`。本轮未接管 CST、运行 worker 或工程；原生关闭重开及工程依赖仍待实际验证。

## 2026-11-06 混合波导端口与离散端口的 F 求解实机验证

- CST Studio Suite 2026.1，CST Automation 插件 0.3.21，Python 库提交 `49b8046`。从空白 MWS 工程调用 `create_waveguide_port_free` 创建相对两侧边界的单模自由坐标端口，与离散端口共存。保存重开后用原生 `Port.GetType` 和 `Port.GetNumberOfModes` 核对类型和模式数。参数化坐标及负参考面距离保存在历史中。模式求解后原生坐标与预期物理端面一致，结果读回准 TEM。去嵌量的电气效果仍待独立对照。
- `configure_fem_solver`、`configure_fd_frequency` 和 `configure_fd_parallelization` 用于全端口四面体 F 求解。原生日志确认多线程块激励和显式低频实算，结果树读回完整复数 S 矩阵。CST 原生固定 50 Ω Touchstone 导出与结果树的频轴及复数矩阵一致到导出精度。两组矩阵均在低频出现无源性超标，原生导出复现该现象。线性残差、网格适配和全带无源性分别验收。
- 模式求解可能改变 `.cst` 的磁盘摘要。持有本轮原生工程句柄的调用方通过已有 `Runtime.save` 记录本轮保存后的摘要，再按登记记录重新解析工程。实机日志、工程和原始数据留在项目内。

## 2026-11-05：实际工程中的验证与迭代技能

- 增加 `cst-in-situ-validation` 并由会话技能引用：复用已有能力，在授权工程工作中按实际阶段记录验证，修复通用缺陷并回馈仓库；保护正在运行的工作和未决调用。
- 新技能通过格式校验、插件打包检查和独立场景审查；这不代表新技能已在实际对话中自动选择，亦不改变任何 CST 接口的实机验收状态。本轮未操作运行中的 CST、worker 或工程。

## 2026-11-05：完整张量会话路由

- `model_api` 显式开放完整 epsilon/mu 张量材料，并在执行批次前使用同一生成器离线验证输入；无效张量不会先执行批次中的其他调用。
- 定向测试及完整离线测试通过；本轮未操作 CST、读取原生材料或求解，实机读回和求解状态不变。

## 2026-11-05：Quiet/Scripting 状态提示与 API 阻塞分开（离线）

- 根据来源截图核对 CST 2026 标题、完整英文正文和两个按钮。诊断沿用同进程 Qt owner 约束，已读完整且精确匹配时保留快照，标记 `scripting_control`，不产生阻塞错误或监测失败锁存。
- 相关离线检查 70 项通过，覆盖精确提示、许可证释放、保存确认、额外正文、截断、读取失败和外来进程。旧回执中未读全的窗口继续按当时证据处理，实际写入与保存回执单独核对。
- 本轮未连接或操作扫描中的 CST、worker、工程或任务记录。真实窗口的采集字段与运行中守卫的分类仍待所属会话实机确认。

## 2026-11-05：HB 独立 Results 自动曲线链（离线）

- 生成可由既有接口注册的 `0D/single_run` Post；离线执行生成源码，验证两组参数各自自动出图，同参数重跑复用正 ID 时保留旧曲线；实际频轴、完整复谱、参数、来源、执行身份和归一化单独归档。
- 缺方向、不同执行、过期 EM、参数不符、无正 ID、冲突重复和发布中断均不冒充完成；没有观察到回调时，托管入口不会把父任务返回当作已生成。托管入口委托原 `run_checked` 保存，记录父任务和历史回执；原生 GUI 路线仍要求工程适配器提供执行身份，由 CST 工作流保存。
- 候选提交快照完整离线检查：1494 项直接通过，2 项创建 Windows 目录联接被沙箱拒绝，单独在隔离目录复核均通过；3 跳过、2 取消选择。12 项新用例；技能与打包检查通过。
- 未连接 CST、部署运行时、绑定当前工程、刷新 worker 或打断扫描；本轮不认证原生参数 getter、回调、结果保存重开、原生同叶参数存储和 Navigator 比较。工程需接入已核验的适配器并按[双参数验收](guides/hb_parametric_storage_and_length_results.md#自动链验收)确认。

## 2026-11-05：EM 改参后的自动曲线与参数历史边界（离线）

- 明确目标为手动改参、重跑匹配 EM 和约定 HB/父任务后，由绑定后处理自动生成当前参数曲线，其他参数曲线持续保留；每参数独立 Results 退路也要求自动生成，不让用户每轮手动导出。
- 区分 HB 原始参数存储、模板 Active/派生关联与 Navigator 比较；记录总开关精确 API 键、自动触发/聚合/安全保存及原生关联仍有缺口。一个正 ID 或缺参数图例不能判定存储关闭，静态快照不能认证原生参数化。
- 新增[自动刷新与参数历史指南](guides/hb_parametric_storage_and_length_results.md)，要求唯一工况叶、完整复数归档、参数/运行/来源/归一化证据及双参数自动刷新、保留历史、保存重开验收。技能入口及已有 HB 指南同步引用。
- 两个技能 quick_validate、22 个本地链接及插件打包测试（1 项）通过。技能情景复核确认退路也自动刷新；指出的运行入口与无人值守保存/聚合缺口已明确记录。检查器依赖仅置于 work 隔离目录，未改公共 Python。
- 本轮仅更新技能、文档与插件；没有连接 CST、操作工程/worker、执行 EM/HB 或部署运行时。上述自动链尚未完成实机验收，原有 9 项未提交改动保留且不纳入发布。

## 2026-11-05：主错误与监测首失败并存的收尾证据（离线）

- 确认主操作先抛异常时，旧 worker 虽用 monitor.failure 拒绝 returned_saved 放行，却未把锁存首失败写入该错误；最后 runtime_diagnostics=clear 不能排除期间已有失败。本聊天仅只读核对指定的保存回执，确认其缺少 session_monitor、completion_evidence 和 worker_runtime 字段；未读取或修改真实会话/DE。
- 新回执保留原 code/message/完整几何或求解 outcome，另记首失败、最终快照和锁存标志；job 记录 prior_status、实际决策/原因及 unknown/launch/监测因素。快照读取失败明确来源为 worker_snapshot_error，首次失败不被后续 clear 覆盖。离线判定也读取回执锁存证据，不能漏传参数后将已有失败改判 ready。
- job.worker_runtime 新增实际 worker PID/解释器/Python、契约修订及所选已加载函数的 code-object SHA256，不用磁盘 HEAD/插件版本冒充运行版本，不回填旧任务。另以两个本机新进程/hash seed 核对所选指纹一致；仍不称跨主机发布签名或完整依赖证明。
- 新增 6 项离线回归；相关 78 项通过，完整检查 1491 passed、3 skipped、2 deselected。独立审查发现首个合成快照错误可能被第二次 clear 覆盖，已修正并新增红绿回归。未放松监测/未知写入围栏，未自动重试/重放、清旧围栏或提升模型/求解验收。
- 旧回执仍不足以判定此次为何 needs_reconcile：不能断言曾出现瞬态弹窗/监测错误或实际加载版本有差异。本轮只补[监测收尾证据](guides/session_completion_monitor_evidence.md)，没有连接当前 DE、触碰 worker/工程或更改旧 job。

## 2026-11-05：旧几何围栏中的显式原生只读审阅（实机反馈）

- 来源模型会话报告：确认无运行/排队/待核对任务、无 Solver 进程、保存摘要匹配且原 DE 仍存活后，仅刷新所属 worker，保留原 DE 和 needs_reconcile；加载 `4500b8f` 对应的显式 inspect/read_only_review 接口并按当前保存摘要提交，job succeeded。
- 原生只读结果覆盖本次所选参数、实体/材料/基准体积及采样点内外归属，来源核对与目标基线一致；文件摘要未变，原 needs_reconcile 保留。此项仅确认该场景中的受限 getter/身份/摘要读取路径及围栏不解除行为，不将查询 job 成功作为几何审批。
- 来源保留原生只读回执和私有几何审阅审计。本聊天仅登记来源反馈，未独立读取原生工程/用户审计，未连接或操作 DE、worker、会话状态与文件；用户工程、参数、实体清单、路径和数据未提交到通用库。
- 不认证完整历史依赖、外部源/缓存有效性、可重建性或 solver；不提升模板注册/执行、通用参数 ByRef 桥接或此前失败操作的实机等级。新基线采纳与后续写入仍须遵守既有审阅规则，未制造 human_reviewed 或自动解除围栏。

## 2026-11-05：几何验证消息分级与显式只读审阅（离线）

- validate_model 不再因原生 INFO 非空把正常 Rebuild 返回当异常；INFO/WARNING 保持 unverified，ERROR/未知或 Rebuild 异常为 error，dependency_validation=unknown。外部模板源缺失与缓存存在均不自动转为几何通过，未按正文猜测严重级别或依赖完整。
- 对正常返回的操作/验证/Rebuild，验证失败保存后带几何回执；worker 核对同任务/操作/工程及保存摘要，原 ready 且无未知/弹窗时，保持 job failed、geometry_verified=False 和 review_required，session 可 ready，不写成功 checkpoint、不通过 depends_on。Rebuild 异常不追加保存；缺回执、保存异常、摘要变化和旧围栏继续保留。
- inspect 增加显式 read_only_review/native_readback/confirm_idle/expected_digest：在旧几何错误围栏中可借用 app 或精确 attach 原 DE，仅读取实际已打开的登记标签及受限原生 getters。核对原进程身份、文件/登记摘要及前后目标，不调用恢复/open/activate/rebuild/save/solve，不消费消息、不清围栏或写 human_reviewed。默认 fenced inspect 仍只返回元数据，读审阅失败保留原围栏/几何错误；实际弹窗失败仍执行原围栏。
- 新增 27 项离线回归；相关 104 项通过，完整检查 1485 passed、3 skipped、2 deselected，独立审查无阻塞发现。未连接或修改真实 CST/worker/session/工程，未替所属会话采纳新基线；此处只确认离线行为，不认证当前缓存、几何、模板或求解有效性。
- 原失败几何 job 缺少新回执时不追溯升为 ready。所属会话可先按[显式只读步骤](guides/geometry_validation_review.md)取得证据，后续新基线采纳仍须真实审阅；不能使用旧摘要或把单独的空闲确认当作已采纳新模型。

## 2026-11-05：首次 import 意图误入旧工程恢复检查（离线）

- 确认旧调用顺序在 copy/register(saved=False) 后恢复原 DE，导致刚复制的首次 import 被 restore_reviewed_projects 当作缺失旧标签，错误要求历史审阅。现将 environment 恢复移至新登记之前，随后刷新当前状态；新意图仍在 native open/create/save 前登记，旧项目 guard 和 adopt 路径不放宽。
- 新增 6 项离线回归，先复现首次 import 恢复误拒绝，再覆盖 MWS/DS 首次 create、真实缺失旧工程仍拒绝、未知 native open 保留 saved=False 意图，以及调用现有 reconcile API 审阅后沿原 project_id inspect 且不重新复制/保存源工程。相关 32 项通过，完整检查 1458 passed、3 skipped、2 deselected；独立审查无阻塞发现。
- 已失败且目标/登记已存在的旧 import 不自动续接、不重复 import/adopt、不覆盖或删 claim。旧回执缺少独立 pre-open/无写入证据时，仍需真实基线与现场空闲审阅；不能用错误文本、复制摘要或本次测试替代。通过现有 reconcile 记录 resolution（非 succeeded），保留原错误和失败副本，再沿原身份检查继续；不手改 human_reviewed。
- 未连接、修改或核对真实 DE/worker/session/工程，未替所属会话恢复或清除 needs_reconcile。本次仅修调用顺序并提供[有审计的恢复路线](guides/initial_project_intent_recovery.md)，不声称原失败 import 已恢复、原生保存或模型/求解通过。

## 2026-11-05：已关闭过程工程退休与独立文件清理（真实会话反馈）

- 来源模型会话报告：在任务全部结束、标签已关闭、无排队任务后，仅退出原 worker，保留原 DE 和恢复引用，加载 `01202cb` / 插件 `0.3.14`。随后通过同一会话提交 close_project(retire=True, expected_digest=..., confirm_idle=True, review_note=...)，一个旧 working 过程副本的 job succeeded。
- 回执 saved/tab_closed/retired=True，environment_closed/files_deleted=False，idle_verified=False 按契约保留；同一记录由 projects 移至 retired_projects，未重开工程。此项确认真实会话登记退休流程，不调用 native SDK，不称本轮取得新的原生关闭证明。
- 随后由所属会话独立核对正式交付摘要、必要内嵌依赖、旧过程副本摘要及待删精确路径和无 reparse，再仅删除已退休的一个过程 .cst 及同名资源目录。原始来源、正式交付、日志、DE 和恢复引用保留。文件删除属于调用方后续清理，不是退休 API 自动删除。
- 本聊天仅登记来源实证反馈，未独立重读交付/原始审计，未访问或操作保留的 DE、worker、会话状态或文件。原退休、清理及最终交付审计由所属会话保留；通用文档不复制器件参数、数据、机器进程或私有工程路径。
- 验证范围仅为真实会话的关闭登记退休与调用方独立 FS 清理；不新增求解验收，不提升模板首次注册、自动回调或通用参数 ByRef 桥接的实机等级。任务已交付后的状态由所属会话维护，本聊天不启动监测或追加求解。

## 2026-11-05：已关闭 working 过程工程显式退休（离线）

- close_project 新增 retire=True、expected_digest、confirm_idle=True 与 review_note，仅在已登记关闭/保存、位于所属会话 projects/<project_id> 过程目录且请求/登记/磁盘摘要相同时移动到 retired_projects。保留 lifetime、原摘要和退休审阅记录；默认 working 关闭不退休、temporary 原规则不变。
- 退役前拒绝外部正式路径、他归属/别名共用、目标缓存句柄、未关闭/未保存、其他排队/运行/未知任务、启动意图、已知弹窗和非 ready。registry.lock 覆盖队列检查及元数据变更；不调用 DE/environment/project/save/close，不删除文件、重开标签或改旧 job。
- confirm_idle 是调用方现场断言，idle_verified=False；tab_closed 根据原关闭登记，不称新原生关闭证明。正式交付及无依赖仍由所属会话独立核对；幂等退休记录不因之后的显式文件清理丢失。原始关闭/失败回执保留。
- 新增 22 项离线回归；相关 35 项通过，完整离线检查 1452 passed、3 skipped、2 deselected，独立审查无阻塞发现。未连接或修改真实 session/worker/DE/工程，未执行真实退休/删除；后续所属会话加载并验证一个过程副本，不把本测试提升为实机生命周期验收。
- 请求与清理边界见[显式退休说明](guides/retire_closed_process_projects.md)，并补齐原生命周期技能与实际 API 的衔接。

## 2026-11-05：会话普通异常阶段与受限堆栈（离线）

- 根据所属会话的 PermissionError 回执缺证据反馈，worker 对非 ServiceError 新增受限 diagnostics，记录异常类型/模块、OS errno/winerror/filename/filename2、最后执行边界、每层最多 12 个文件/函数/行号及最多 3 个原因异常。无 OS 路径则保留未知，不序列化 locals、请求参数或源码，不追溯改写旧 job。
- 标记工程恢复/打开/激活/登记、History 执行、原生保存、保存后摘要、保存登记和 checkpoint 写入边界。stage 只说明最后进入的边界，不能证明是否发生副作用；不据 PermissionError、摘要未变或重试成功猜测 OS 根因。
- 新增 11 项离线回归：保留原 ServiceError 与 returned_saved 规则，普通错误仍 failed/needs_reconcile；History/保存已执行但 checkpoint 拒绝时不重试。独立审查发现异常格式化可能再次抛错，已补安全 str/repr 及整体诊断降级、主异常/原因格式化失败红绿回归，确保诊断不绕过原失败围栏。
- 完整离线检查 1430 passed、3 skipped、2 deselected。未连接 CST、检查或修改运行中的 worker/DE/器件工程，没有重放 History/HB、改旧任务或执行 reconcile；实机诊断字段由所属会话以后在空闲加载后观察，不打断当前任务。
- 使用与落盘能力边界见[普通异常诊断](guides/session_exception_diagnostics.md)。本次不声称已定位原 PermissionError 的文件、调用阶段或具体 OS 原因；持久审计文件自身不可写时，也不能保证异常能写入同一受拒绝文件。

## 2026-11-05：工程绑定的存储参数 ByRef 桥接（文档/离线契约）

- 根据本机官方 Project/GetParameterCombination 的 Variant ByRef 名称/double 数组及 Boolean 返回契约，生成显式 schematic 查询宏，拒绝 Run 0/非 Schematic ID，不猜 Python 代理的输出参数形式。宏先核对实际工程资源主目录，再查询固定正 ID；使用唯一请求 token、UTF-16 code-unit hex、完整计数/结束标记和有限数值回执。
- 仅通过所属会话 circuit/build/read_run_parameters 暴露；要求原 worker 已有 app/缓存工程句柄、未关闭登记及存活原环境身份，不走 Runtime.project/environment 恢复，不 attach、重开标签、创建/关闭 DE 或保存/求解。通用服务没有可信 host 借用上下文时，在 app_factory 前拒绝，JSON 无法伪造授权。
- confirm_idle=True 只是所属调用方的空闲断言，idle_verified/native_bridge_verified/solver_verified 保持 False。调用清单/生成宏与原始输出单独留审计；不覆盖原失败日志，不把解析成功或已有曲线提升为桥接、模板、缓存或求解验收。
- 新增 26 项离线回归，完整检查 1419 passed、3 skipped、2 deselected。独立审查发现并修正 code-unit 端序及通用服务连接/关闭路径问题，分别补红绿回归；再次审查无阻塞发现。未连接或操作当前 CST/worker/工程，实机宏编译、返回值及回调嵌套重入仍待所属会话在空闲时分别核验。
- 所属会话可按[工程绑定桥接说明](guides/project_bound_run_parameter_bridge.md)选一个真实正 ID 作首次只读核验；示例 ID 不保证存在。此方案不证明可在运行中的 evaluate 内嵌套调用宏，不触发扫描，也不改变既有失败 job 或恢复状态。

## 2026-11-05：Update 异常审计与存储运行参数绑定（离线）

- 所属模型会话报告父任务 Update 抛错、后处理缺点且未保存；本聊天只读检查指定模板源码，确认存在接受未枚举正 ID 和按最大编号回退的分支，未以实际存储参数组合约束。原始错误仍由所属会话保留；具体缺点的因果关系及缓存复用正确性继续以其独立原生读回为准。
- Update 抛错新增独立 circuit_task_update_failed、update_call_state=raised、failure_stage、原始异常及日志增量/磁盘摘要审计。execution_returned/saved 保持 False，save_policy=deferred_until_idle，不把 Python 接到异常当成 DE 空闲，不盲目保存、解除围栏或改历史 job。正常返回保存路径的状态规则不变。
- 新增纯数据选择器及显式存储参数 reader 的原生桥接：所有必要曲线必须有共同正 Schematic ID，参数组合必须实际读取并匹配；别名只能唯一匹配，显式固定 ID 不符直接拒绝。未知、歧义、跨域与缺参均拒绝，不使用 last/max。可定位合法复用的旧 ID，但不证明完整缓存或本轮新求解。
- 新增 15 项离线回归，先复现身份选择及异常阶段问题再修复；完整回归 1393 passed、3 skipped、2 deselected。独立代码审查无阻塞发现。新接口、模板实际执行及异常后原生恢复未在本聊天实机验收。
- 未连接 CST、改当前 worker/DE、修改器件模板/工程、运行或重放扫描；没有复制器件参数和原始数据到通用库。通用处理规则见[Update 异常与结果身份](guides/circuit_update_and_result_identity.md)。

## 2026-11-05：已返回保存但数值未验证的电路状态规则（实机反馈）

- 来源模型会话报告：用户明确核对全部登记工程的保存摘要及空闲基线后，仅做一次人工恢复；随后在保留原 DE、工程和恢复引用的条件下退出旧 worker，加载 `10030de` / 插件 `0.3.10`。
- 新 worker 执行一轮叶 HB：调用已返回并保存，job 仍为 failed / session_circuit_failed，内部保留 circuit_result_unverified；session 保持 ready，没有再次因数值证据不足误入 needs_reconcile。同一会话随后接受父任务，反馈时父任务仍在运行。
- 这条实机证据仅验证“明确返回保存的未验证结果不再误锁会话”及原有失败审计/未验证结论仍保留。来源另报原生固定 Run ID、输入身份与谱独立读回；这些单列证据不将本轮叶任务提升为 solver 通过、数值收敛、模板注册/执行通过或父任务完成。
- 以上为所属模型会话的实机反馈，本聊天未独立重读原生工程/日志，未连接 CST、刷新当前 worker、修改工程或再次 reconcile。原始 job 与 circuit_runs 审计由所属会话保留；通用文档不复制器件参数、原始数据或机器进程标识。

## 2026-11-04：已返回保存的 circuit 叶任务状态分离

- 电路运行在原生 update_task 返回后记录 execution_returned，保存后记录 project/SHA-256；先记录返回保存，再读取日志/结果，不以旧父日志或曲线存在冒充本轮验收。
- 只有明确 circuit/solve/run_task，且工程、任务、运行身份、保存摘要/登记摘要/磁盘相同，无弹窗失败/未知前序/启动意图、原状态 ready，才保留 failed job 的完整原 outcome 和 returned_saved/review_required 并保持 ready。结果仍可 unverified/failed，不提升数值、原生完成或验证等级。其他操作、缺回执/保存失败/摘要变化及已有 needs_reconcile 继续围栏。
- 新增 21 项离线回归，核心问题先复现再修复；整合远端 main 后完整离线回归 1378 passed、3 skipped、2 deselected。独立代码审查无阻塞发现。未连接 CST、改写当前 job/session、reconcile 或刷新任何运行 worker。
- 更新技能与同 DE 加载边界：只由所属会话在明确空闲后刷新 worker，保留 DE/PID/原恢复引用。加载不自动解除历史 needs_reconcile，不把数值复核变成逐轮空闲审批。

## 2026-11-04：M0D 执行后多输出注册的受控替换

- 来源实际 v11 Summary 仍为一个 Python 注册模块，但多 yield 后追加了输出清单。
  原固定 15 行检查错误拒绝此状态；现在按明确计数、单模块所属前缀、唯一输出名及
  已观察的末尾标志解析，未知展开格式和多模块继续拒绝。
- 离线先复现后修复，覆盖当前完整摘要、过期摘要拒绝、计数/身份错误、纯读取不写入，
  以及执行后替换的原生归档边界替身。只读实际原生资源已解析成功，未改器件文件或
  触碰 CST；源码、设置、Summary 原始字节仍全部进入摘要。
- 输出索引存在不证明回调成功、指标正确或原生替换已验收。器件侧保留原失败资源、
  日志及表示约定，随后按授权仅重评估已有 HB 数据；本 API 不启动求解或模板执行。
- 完整离线回归 1355 passed、2 deselected，保留 9 项既有端口朝向提示；本聊天
  仅只读核对原生资源格式，原生替换和 Post 回调验收继续由器件会话负责。

## 2026-11-04：协同合并后的离线回归

- 保留正式工程路由、日志范围、消息回执、模板注册及本轮运行身份/网格边界更新，
  解决文档与模板测试的合并冲突。测试辅助函数改名，避免本机 pytest 将其当作旧式
  setup 钩子。完整离线检查 1345 passed、2 deselected；9 项既有端口朝向提示。
- 本聊天未连接 CST、刷新运行 worker 或修改器件工程；实际模板执行的新问题
  仍由独立修复和原始证据核验，不以合并回归代替原生运行验证。

## 2026-11-04：外部正式工程的 circuit 路由衔接

- session circuit 原先将已授权的正式工程再次按 workdir 拒绝。现仅将同一登记 project_id/规范路径及精确授权传给 handler；默认服务、输出目标、模板/模型输入的原 workdir 约束保留。
- 新增离线回归覆盖 external formal inspect/run_task/read_results、缺失/伪造/他工程授权、不可扩展导出目标、默认服务及可信 grant 的单工程绑定。借用 app 不关闭原会话；无真实 CST 调用。
- 合入远端模板注册实现并补齐测试请求 project_id 后，完整离线回归：1345 passed、3 skipped、2 deselected；没有连接 CST 或刷新运行 worker。
- 叶任务日志没有新片段时 completed=False；历史父日志错误单独保留，不冒充叶任务错误。新增回归覆盖未更新父日志、追加成功叶片段和本轮真实错误。不以可读曲线数量提升执行验收。

## 2026-11-04：消息级别、保存回执、正式路径与 HB 放行门槛

- RunContract 保留结构化消息，INFO 不因非空失败；WARNING 保持 unverified，ERROR/未知消息保持 failed。提交前先确认审计可写，再保存前队列，提交后队列不按正文去重；没有原生 Run ID 绑定时仍明确范围未知。原生完成、网格、数值与 API 状态分别记录，不以文件变化替代验收。
- session 非成功求解只有在明确返回、同工程保存摘要与磁盘一致且无未知前序/弹窗失败时，才保留 failed job 的完整回执并保持会话可用；没有改变已有 needs_reconcile 或历史失败 job。ready 不代表警告已审阅，依赖任务须由调用方停止/跳过。
- create/import 新增精确授权的 working_path，adopt_project 支持核对摘要后原位登记已有正式工程；拒绝覆盖，保留会话/project_id/恢复身份，失败打开仍占用目标直至明确核对。仅离线验证，未移动、重开或接管实际运行工程。
- HB 技能增加逐被动块实际 0 Hz/截断混频覆盖、独立来源与拓扑检查、双向代表工况先验、首错停组和无本次输入跳过模板。低频推导零端点标为近似，不称独立 DC EM；这些是编排门槛，不冒充现有配置封装已自动执行。
- 新测试均观察 RED→GREEN；最终完整离线回归 1311 passed、3 skipped（MCP extra 缺失）、2 deselected（实机/UI 未执行）。代码/技能独立审查发现的前置审计与失败路径占用问题已修复；插件打包测试通过。
- 本会话没有连接 CST、重算 EM/HB、改原任务结果或部署运行 worker；实际模型的日志/矩阵/工作点与 DC 覆盖复验由所属会话负责。首次 Python 模板注册的另一机实现仍未找到，不因本次状态修复宣称已实现或验证。

## 2026-11-04：Qt glow 正文预算误报修复

- 对精确装饰窗增加正文读取前的结构识别，匹配同进程 Qt owner、已知相同创建身份与无原生子控件；保留原始快照和结构证据，不把未读正文标为读取成功。其他模态/未知窗口继续走原检查。
- 新增 11 项离线回归先复现再通过，相关 40 项通过；完整离线回归为 1274 passed、3 skipped（缺 MCP extra）、2 deselected（实机/UI 未执行），独立代码审查无阻塞发现。
- 来源会话有限跟进：只刷新已核实空闲 worker，保留原 CST DE/保存副本；原生 inspect 与 circuit inspect 均 succeeded，报告时 EM 仍在运行且 runtime_diagnostics.state=clear，未再出现此次 Qt 装饰窗误报。不是 EM/HB 完成、收敛或器件验收；本会话未操作 CST。
- 本次实际版本依据来源 Model.log/output.txt 为 2026.2 Release from 2025-11-28 change 1505684；doctor 的 CST2026 目录名不作版本替代。迁入包的 2026.1 记录属于早先独立阶段。
- 实现及证据边界见[守卫修复说明](guides/qt-glow-budget-repair.md)；具体工程参数、数据、进程与 job 标识未复制入通用库。

## 2026-11-03 仓库、插件与本项目环境更新

- 拉取 origin 后，将 `origin/codex/nine-skill-plugin` 的 `39e34bb` 合并到当前 API 修复分支，保留 `92b7308` 及之前的消息三态、Pass 轴结果、采样计划等改进；没有切换或重写 main。
- 合并保留严格装饰窗证据与 PID 创建身份，以及远端 scripting/save overlay 和消失窗口复查。旧窗口替身测试补充显式可见性边界，避免读取虚假 HWND 的真实状态；冲突解决已独立复核。CI 核心测试安装 plot extra，以覆盖新增共享样式测试。
- 本项目 `.venv` 安装 editable `cst-automation[plot]`，版本 `0.2.0.dev0`（开发版）；`pip check` 无依赖冲突。使用 `-I` 隔离导入确认模块来自本仓库，普通导入未加载 cst SDK。未修改公共 Python 或全局 MCP 配置。
- 完整离线回归：929 passed、3 skipped、2 deselected、23 warnings。3 项 MCP 测试因本项目 Python 3.9 环境未安装 MCP extra 跳过；GUI/cst_live 均排除。没有连接 CST、读取实际工程、启动求解或中断其他会话。
- 插件构建通过九个 skill、25 个文件、相对链接和公共内容检查；使用现有本地 marketplace 更新已安装 `cst-automation@cst-automation-local` 至 `0.2.1`，状态 installed/enabled。目标缓存 25 个文件与构建逐项一致，包含九个 skill。旧 marketplace 源备份保留在本仓库 work/plugin-update 下；未卸载其他插件。
- 插件与 Python 库独立版本。安装状态与缓存一致不证明当前聊天已重新加载新技能；需新建聊天或按宿主提示刷新，必要时重启桌面应用。

记录 `cst-automation` 0.1.0 的拆分历史及后续验证。几何 API 检查、结果读取和真实 CST 求解分开判定。本地运行与 GitHub Actions 运行分别记录，不能相互替代。

## 2026-11-02 CST 2026 API 离线修复

### 指定缺失样点的纯离线计划与频点核对

- 本机官方 FDSolver 帮助核对 ResetSampleIntervals、AddSampleInterval、ForceRecalculateOldSamples：区间重设不清除已存结果，强制重算不能理解为仅算新增 Single 点；False 也不是实际点集保证。
- 新增 `cst_solver.sampling.plan_missing_samples` 和 `assess_sample_execution`。无 SDK/文件/宏/solver 操作；显式单位、已有结果未知与空集分开，只有调用方核实缓存及采样上下文时给出条件性预期新算点。核对只接受同周期实际日志观测频率，abort、频点 mismatch 与 accuracy not_assessed 分开保留。
- 新增 22 项离线测试；完整回归 `.venv/Scripts/python.exe -m pytest -ra --disable-warnings --basetemp=work/adaptive-results/pytest`：**594 passed, 2 skipped, 1 deselected, 9 warnings**。复核无待修问题。未打开工程/结果/在写日志，未连接 CST、启动求解或改动安装环境。
- 来源会话报告的错频中止周期不作为目标低频精度通过/失败。本轮没有读取具体诊断证据文件，没有实现原生日志语法解析器，也不声称 False 的后续尝试已验证。

### 消息三态契约修复与推送前验证

- 实施 not_read/read/read_failed：messages_clean 为 bool|None，未读不再由空列表判成功；保留部分迭代消息与读取异常，明确 caller/callback/sdk_pending_queue 来源。原生 solver、原生日志警告和 mesh 收敛无读取证据时仍为 unknown。
- 新增 23 项离线测试，包含 RunContract/run_checked 禁读及成功/失败读取、JSONL、独立运行之间状态隔离、错误参数不触发提交、后端/服务落盘/MCP 查询传播，以及保存失败仍保留运行契约和 run token。
- 完整回归：`.venv/Scripts/python.exe -m pytest -ra --disable-warnings --basetemp=work/adaptive-results/pytest`：**572 passed, 2 skipped, 1 deselected, 9 warnings**。2 项 MCP 协议/stdio 测试因缺少 extra 跳过；服务及 MCP dispatch 状态传播测试已通过。没有安装依赖或改变当前运行环境。
- 代码复核发现保存失败会丢运行证据，已补失败回归并修复；当前改动不宣称真机验收。用户授权提交和推送当前专用分支，未授权合并 main 或部署安装环境。
- 来源会话只读确认 `Mesh\Information\Element Information\Low Quality Elements` 可原生可视化定位；数值 ID/坐标/质量导出仍未证实，详见网格诊断能力文档。本会话未连接其检查会话。

### 联合枚举与 Pass 轴读取补充

- 实现 `Result.enumerate_result_paths`、`read_adaptive_s_parameter` 和 `read_adaptive_s_parameters`，通过独立 mixin 接入，保留现有树枚举签名；普通 S 参数发现限制到主频率结果树。
- 新增 45 项离线测试，使用显式 results/modeler 替身，禁止隐式 SDK 加载/会话构造。覆盖重复路径来源合并、枚举中断/失败、modeler-only 路径、同一 run 下逐轮复数数据、显式/错误/当前别名 run、Pass 轴与非法数组、参考阻抗原样保留及未知归一化、单位原文与冲突、部分读取错误、空结果及不混入普通频率批量读取。
- `.venv/Scripts/python.exe -m pytest -ra --disable-warnings --basetemp=work/adaptive-results/pytest`：**549 passed, 2 skipped, 1 deselected, 9 warnings**。MCP extra 缺失和 GUI 排除与前次一致；测试产物在 work/。这不增加原生 readback 或求解验收等级。
- 未连接、启动、关闭 CST，未读取来源工程，未修改全局环境或插件缓存。原生参考阻抗的数据形态、工程身份对应和新接口完整闭环仍需在已授权主机环境串行验收；来源会话此前已核实的路径/轴语义与本轮实现的离线测试分别记录。

### 前序通用修复记录

- 分支：`codex/cst-2026-offline-api-repairs`；本段为首次推送前验证记录，后续交付以 Git 提交为准；未更新全局安装或插件缓存。
- 本轮不连接、启动、关闭 CST，不读取或修改另一会话工程，不中断其求解。未检查或声称全机空闲。
- 本机官方帮助核对了点端口 Voltage/Current、picked 参数、面端口不同的幅度方法、CircuitProbe/Net 对象及 continuation 的文档边界。
- 新增 17 项离线回归：点端口宏、执行器选择与不重试、CircuitProbe/Net 宏、Delta S 多频率/连续轮次判定、装饰窗与未知状态、确认前 PID 创建身份复核、主机预检查拒绝与服务错误码。修复一个既有测试对临时目录父路径为 ASCII 的假设，以支持在本仓库中文路径下运行所有测试产物。
- 本仓库 `.venv` 实际为 Python 3.9.18；补齐该隔离环境的 pip/NumPy/pytest，未修改公共 Python。执行 `.venv/Scripts/python.exe -m pytest -ra --disable-warnings --basetemp=work/api-offline-repairs/pytest`：**504 passed, 2 skipped, 1 deselected, 9 warnings**。2 项 MCP 协议/stdio 测试因未安装 MCP extra 跳过（该 extra 要求 Python >=3.10）；1 项 GUI 测试不运行；9 项为既有端口朝向提示。`git diff --check` 无错误。
- 离线 `doctor --json` 发现本机 CST 2026 与 cp39 ABI 匹配，状态为 `not_probed`；没有执行 `--probe`，不声称 SDK 导入、IPC、许可、readback 或 solver 已验证。
- 本轮没有找到公开显式选择 CONTINUE 的已文档化 Python/VBA 方法；ForceRecalculateOldSamples/AcceleratedRestart/resume_solver 不能作为该能力的证明。未实现或声称原生网格 continuation 可用。
- 主机 preflight 为新增 opt-in 入口，既有 setup/服务尚未迁移；收敛评价器处理调用方提供的证据，未实现原生自适应结果提取；Qt 非标准确认按钮与不可读正文仍上报，不自动处理。新增连接、暂停、停止案例仅记录来源会话报告，未复测。
- 调用示例、官方帮助相对路径和逐项真机待验清单见 [API 修复说明](guides/api-offline-repairs.md)。真机验收须等待其他求解结束，并持有全机串行锁、核对 PID+创建时间、在可访问主机环境执行。
- 来源会话后续报告：中止完成、控制器退出，但恢复最后成功解后出现离散面端口解加载失败，原生 state 为 ERROR，不计完整矩阵或求解通过。ItemMeshSettings 为上下文变更调用，误作 getter 属使用方语义错误；Python 侧观察到 bool 不证明 VBA 可赋值表达式合法，后续该表达式已报 10091，而原 With 内调用形式可配合读回。求解器自动生成特殊体不支持 simple bounding box 的情况须与普通几何损坏分开记录。以上仅补充记录，未复测；主任务即将继续，不据此认定全机空闲或取得真机使用授权。
- 逐轮结果结论更正（来源会话真机只读核实，本会话未连接）：Model3D 树枚举可发现 Python results 树列表漏列的 `1D Results\Adaptive Meshing\f=<frequency>\S-Parameters\S<i>,<j>`；这些条目可由 Python results 按已有 run ID 读取，xlabel 为 Pass、y 为每轮复数 S。来源会话已全量读回并复现原生 Delta All S、核对末轮主矩阵及归一化。不能再以 run ID 未增加或 Python 树漏列断言无逐轮数据；后续联合枚举须显式使用已授权会话，不能隐式连接。本轮仅记录通用语义，未新增实现或纳入具体矩阵数据。

## 2026-10-27 维护验证

- **Git 来源已恢复**：本机目录原为不含 `.git` 的源码副本。先保存文件快照，再在 `work/maintenance-20261027/upstream/` 克隆完整仓库并恢复根目录 Git 元数据；重建索引时保留全部工作文件。维护前远程 main 为 `07279b078af3484f6f0ad8c0ed6c9ed02db702f5`。该提交的 [Actions 40395424088](https://github.com/Ding-zhenke/cst-automation/actions/runs/40395424088) 已成功；这不是当前维护改动的 CI 结果。
- **维护提交的远程 CI**：分支 `codex/portable-environment-validation` 的提交 `adf187b3fa254554effb7d328fd8e7a71b529538` 已推送；[Actions 40399304203](https://github.com/Ding-zhenke/cst-automation/actions/runs/40399304203) 的 Python 3.9、3.11、MCP 和 build（包含全新环境的 wheel 安装与 stdio 检查）四个 job 全部成功。修复及本记录通过 [草稿 PR #2](https://github.com/Ding-zhenke/cst-automation/pull/2) 提交审阅，未合并到 main。
- **环境与 CLI**：发行包的兼容 `config.py` 不再携带机器路径；离线检查对缺失 SDK 目录、未发现 SDK、选中安装已知 ABI 不匹配报告 `unavailable` 并退出 1。`doctor --json` 已支持，默认仍输出 JSON。测试验证了未配置时发现安装、显式无效路径不回退、JSON 输出、退出码及自定义 SDK 的 ABI 归属。
- **离线回归**：仓库 `.venv`（Python 3.13.9，不继承系统包）执行 `python -B -m pytest -o addopts='' -m "not gui" -q -p no:cacheprovider --basetemp=work/maintenance-20261027/pytest-full`：**490 passed, 1 deselected, 9 warnings**。警告仍为端口默认朝向提示；GUI 用例未运行。
- **SDK 导入**：显式设置 `CST_INSTALL_PATH=E:\CST2026` 后，Python 3.13.9 / CST 2026 的 cp313 匹配，`doctor --probe` 实际导入 `cst.interface` 和 `cst.results` 成功，状态为 `importable`。该路径是本机验证参数，不是发行默认值；不代表许可证、readback 或 solver 已通过。
- **MCP stdio**：新增真实子进程集成测试，使用 MCP Python SDK 1.30.0，完成初始化、9 个工具发现、读写注解、能力调用、未知工具/参数错误、假后端任务排队/状态/结果与关闭工程。测试阻止实际加载 CST，且检查请求 `run_id=7` 能原样返回；同时修复 FakeBackend 固定返回 run ID 0 的问题。通过的是 stdio 与 fake 任务链路，本包没有实现网络传输入口，不声称网络传输通过。
- **发行制品**：构建 wheel 和 sdist 成功；构建后端最低版本改为支持 SPDX license 字符串的 `setuptools>=77`。制品不含 `work/`、`.venv/`、源码备份或 Git 元数据，wheel 内配置无机器路径。
- **干净安装**：`work/maintenance-20261027/release-venv/` 由 `venv` 新建，`include-system-site-packages = false`；安装刚构建的 wheel 及声明的 NumPy/MCP 依赖。独立目录中清除 `PYTHONPATH`，四个包的加载路径均在该环境 `site-packages`，普通导入不改 `sys.path`、不加载 `cst`。曲线调用、缺失 SDK 的 doctor 退出码 1、安装版 stdio 握手/9 个工具发现/结构化错误均通过。可复用检查脚本为 `scripts/verify_wheel.py`；CI 的 build job 也执行该隔离安装检查。
- **尚未验收**：真实 CST 几何重建、实际消息/UIA、S 参数结果树发现、远场导出、solver，以及相邻领域仓库联调。具体几何参数、端口及阶段证据方案见 [真机验收预览](REAL_CST_ACCEPTANCE.md)，等待用户审阅后才构造几何。运行中取消接口仍未开放。
- 原始快照、构建日志、环境报告及隔离安装报告保存在被忽略的 `work/maintenance-20261027/`；本轮不修改相邻仓库或用户全局 MCP 配置。

## 2026-11-04：F 求解器 CPU 并行配置


- 新增 `configure_fd_parallelization`、显式会话路由/整批预检、配置回执及类型存根；
  命令依据本机 CST 2026 官方 `special_vbasolver_fdsolver_object.htm`。
- 定向 104 项通过，覆盖三种 FDSolver 设置、稀疏更新、非法输入不接触工程、
  后置错误阻止先前几何写入、部分失败不重试及不提高验证标志。
- 接口开发阶段本聊天未连接 CST、修改器件文件或启动求解。后续器件会话实际
  调用新 wrapper，保存历史包含三种 FDSolver CPU setter，随后的本轮原生日志
  明确记录 CPU block excitation 线程数；确认新入口实际触达并用于运行。
- 设置 getter 仍不受支持，配置回执的验证标志保持 False；日志证据单独记录，
  不外推为 GPU/HB 并行或网格收敛通过。器件参数及原始工程证据留在私有项目。

## 2026-11-04：原生运行身份与 Qt 结果失效弹窗

- 实际同参数网格重跑复用/覆盖了已有正数 3D Run ID；正 ID 不能独立充当不可变
  执行身份。更正 `result_conventions` 说明与结果技能，要求保全原始复数结果、
  原生日志、参数及工程/结果摘要。既有指纹比较及求解验收谓词保持原义。
- 真实 Qt `Results May Get Incompatible With Model` 通过目标窗口的 UIA 选项选择、
  独立重读选中状态与 Invoke 确定完成处理，原 SDK 挂起期间未追加 SDK 写入，
  guard 继续保留 `blocked_by_dialog`。原调用返回后核对已保存历史、几何和摘要，
  未盲目重放；未使用 Computer Use 工具，未将缓存目录存在提升为缓存内容验收。

## 2026-11-04：现代网格器控制边界调查

- 官方 Mesh Object 帮助说明部分旧控制仅用于 legacy mesher，现代全局与局部设置
  主要由 MeshSettings/ItemMeshSettings 按类型和组管理。现有全局密度/材料设置
  仍经旧 Mesh 路径，新增明确回执分类和警示，不声称活动 HF Tet 组已读回。
- 局部 Solid 尺寸限制与 MeshAdaption3D 自适应为不同路径；观察到自适应增密
  不证明请求的全局密度生效，也不证明 ΔS 已通过。未在本聊天触动器件 CST，
  未猜测新的 HF Tet 组名/键或读取内部缓存来冒充原生设置 getter。

## 迁移阶段历史记录

以下为拆分阶段保留的历史结果，环境、依赖版本与当时的推送状态不能作为本轮的新证据。

## 2026-11-03：工程复用与临时标签（离线）

- 隔离 HEAD 加本次修改的完整默认离线检查：824 passed，另有 3 项目录链接/MCP 子进程权限受限；这 3 项在批准环境重跑为 3 passed。针对性 22 项和插件打包 14 项通过。未连接 CST。

- 新增重复工程/源路径预检（含排队意图）、只读参数/实体/点查询、精确标签关闭与
  临时工程退休审计、离散扫描配置及 MCP 操作枚举一致性检查。
- 回归覆盖查询不写历史/重建/保存、关闭前保存、关闭后打开列表核对、失败保留状态、
  临时文件删除后的基线恢复、扫描阶段重试去重和 fake worker 全流程。
- 使用仓库 `.venv`，测试数据限定在本仓库 `work/session-discipline-fix`。本轮未启动
  CST、未做真机读回或求解；原生 API 调用仅依据本机官方帮助及隔离替身测试。

## 2026-10-30：通用电路参数研究（离线）

- 新增纯数据参数研究校验、CircuitAPI.run_parameter_study、StudyResult 历史归档/过滤/比较与保存结果读回接口；服务和 MCP 路由复用唯一 worker。具体 schema 和边界见 [通用参数研究](guides/circuit_parameter_studies.md)。
- 已观察 RED→GREEN：新模块缺失、参数写入读回不一致、源数据未在写图前落盘、缺少服务/MCP 路由。针对性测试覆盖 EM 重建/求解先于电路、重复工况/批次不覆盖、失败中止且保留原始复数数据、单位不一致和归档摘要不匹配拒绝、原生汇总数组读回不一致不通过。
- 无新 CST 进程、真实工程、EM/HB 求解、几何重建或原生保存关闭重开；不提高现有运行契约、EM 块映射、各电路求解器或 .cst 单文件打包能力的实机验收等级。第一版 EM 每点重算；全局参数单位由调用者确认；双向瞬态联合继续用既有接口。
- 独立只读代码审查发现三项 Important，均用 RED→GREEN 回归修复：全目录/日志指纹不能证明指定 EM 数据已刷新；原始结果参数必须与当前全局参数相符；整批预检复用原生属性写入的静态限制。EM 现要求指定原生数据文件更新、原生 SUCCESS 及 EM 结果参数匹配；同值重复计算可依靠新文件证据通过，不要求曲线数值改变。
- 最终完整默认离线回归：**874 passed, 2 deselected, 9 warnings**，29.46 秒；2 项为按默认 marker 排除的实机/界面检查，9 项为既有端口方向警告。包含 MCP stdio 握手。日志 `work/circuit-study-20261030/final.log`；修改前相关基线 87 passed，首次实现相关检查 119 passed。`git diff --check` 无格式问题。既有未提交修改原样保留，不提交/推送其他工作。


## 2026-10-27：多对话持久 CST 会话

- 新增显式 SessionManager、每会话独立 worker 与 DE、固定绝对根目录、私有恢复引用、
  原子文件队列、完整进程身份校验、请求/阶段去重、检查点恢复及人工核对出口。
  旧 RunService 临时模式不变；MCP 显式注册七个工具，也可用会话 CLI，无全局配置修改。
- 实机空环境验收：双会话分别创建不同 DE；客户端退出后环境保留；连续调用复用
  原环境；只终止测试 worker 后按同一 PID、进程启动时间和镜像路径重连原 DE；
  关闭 A 后 B 仍能调用，最后分别关闭测试环境。另用 work 内空 MWS 工程验证创建、
  保存、worker 丢失后的原环境/原文件复用与关闭；没有添加几何、端口、材料或求解。
  记录：`work/session_validation/native_verified.json`、`native_project_verified.json`。
- 初始沙箱 detached 启动在命令返回后未发现存活进程或启动回执；在允许独立进程
  生存的执行环境复核通过。启动入口保留权限边界，不自动换目录或接入任意已有 DE。
  不能将一次 Popen 返回 PID 当作可常驻证据。安装/ABI doctor 保存在同一目录。
- 新测试先失败再实现，覆盖双会话/同名工程、实际子进程、客户端重建、worker 丢失、
  原请求和阶段重发、别名请求冲突、创建未知窗口、保存检查点回执丢失、失败屏障
  跨重启、关闭排队、凭据边界与 CLI/MCP 接入。人工恢复只采纳经核对的文件基线，
  不把未知执行升级为成功；不可接管另一活动会话环境，可放弃未落盘的工程意图。
- 独立代码审查发现并已修复：关闭请求覆盖失败屏障、人工恢复误接管其他会话 DE、
  首次工程未保存后无恢复出口。三个针对性回归测试独立复跑通过，无新增 P1/P2。
- 最终全库离线：`.venv/Scripts/python.exe -m pytest
  --basetemp=work/session_validation/full_suite_final` → **776 passed, 2 deselected,
  9 warnings**，警告为既有端口方向测试。日志 `full_suite_final.log`。受限环境的前次
  全库运行有两项 CreateJunction 权限失败和 stdio 握手超时，未改测试时限；允许相关
  本机操作后通过。一次中间全库运行遇到 fake worker 意外退出，无 traceback，原因
  未确立；最终全库与独立聚焦测试通过，保留 `full_suite_native.log`，不宣称已证明
  任意宿主/沙箱条件下进程永不退出。持久恢复负责在进程确实丢失后核对并续做。
- 实机边界：原生 DE/空工程生命周期通过；非空几何阶段、繁忙求解中断、真实 circuit
  持久借用及 solver 结果验收仍未执行。history/参数阶段 rebuild 和消息检查已接入，
  但不能从离线测试或空工程验收提高这些能力的实机证据等级。SDK 未知副作用进入
  needs_reconcile，不承诺任意命令 exactly-once。

## 2026-10-27：剩余 HB 与后处理改动提交前检查（离线）

- 独立代码审查后修复模板暂存目录连接越界、CST 不支持的默认/仅限位置入口参数，以及 Results 文件夹替换可能删除子节点的问题；补充先失败再通过的回归测试。明确 HB 数值沿用目标任务当前生效的单位，不自动切换局部单位。
- 仓库 `.venv`（Python 3.11）完整离线测试：`755 passed, 2 deselected, 9 warnings`；排除 `gui/cst_live`，警告来自既有端口方向测试。MCP stdio 握手与目录连接测试在允许相应操作的隔离进程中通过。日志及 JUnit 记录保留在忽略目录 `work/verification_20261027/`。
- 按 `pyproject.toml` 声明的构建依赖，在仓库内临时隔离环境中成功构建 wheel 与 sdist。未修改公共 Python 环境。原 `.venv` 的旧 setuptools 不满足构建声明，未将其无隔离构建失败算作通过。
- 本轮未启动 CST、rebuild、原生工程读回或求解，离线检查不提高实机验收等级。skill 只保留通用操作与证据要求，不提炼用户私有模型参数；指南中的固定扫描范围改为调用方提供的数组。

## 2026-10-26：原生 HB 扫描及后处理辅助接口

- 将实际工程中使用的 Spectral Lines 基频/阶数、原生 Parameter Sweep 序列、指定 result ID 的复数谱线提取、Results 实数曲线写入及现有模板源码替换整理为通用代码接口。保留工程参数表达式，不固定模型路径、频段、端口、RF 方向定义或归一化公式。
- 离线测试覆盖输入预检、错误任务类型、表达式保留、原生序列构造、显式运行身份、谱线缺失/重复、dB 禁止重复取对数，以及旧叶删除连带删除信号文件后的替换顺序。嵌入模板测试覆盖元数据保留、摘要冲突、越界路径和无效源码拒绝；只静态检查，不执行模板。
- 本轮没有启动 CST、computer use、EM 或 HB；不将历史实际工程的求解验收转记为这些封装已完成实机验收。默认返回 readback_verified=False / solver_verified=False；模板替换还返回 native_save_required=True。用法见 `docs/guides/native_hb_postprocessing.md`。

## 2026-10-23：T 求解器原生磁 Gyrotropic 接口（仅离线）

- 新增 `setup.create_material_gyrotropic`，Normal + Gyrotropic + SI 模式；Larmor/旋磁角频率为 `larmor_omega/gyrotropic_omega`，单位 rad/s，避免与完整 Tensor formula 的 `f`（Hz）混淆。两个频率、阻尼、高频相对磁导率、电导率、介电常数及三分量方向均支持项目参数表达式。数值范围和单位方向校验先于访问工程；仅提交一个历史块。
- 新增 30 项 Gyrotropic 测试，覆盖 SI 命令映射、单位刻度、默认与反向偏置、表达式保留、角频率不隐式换算、颜色及非法输入。材料相关及表达式/失败/环境回归共 **218 passed**。类型存根语法及 `git diff --check` 另行检查。
- 全库默认离线检查为 **728 passed，1 failed，2 deselected**；唯一失败是 `test_circuit_stdio_handshake_and_offline_preview` 的 8 秒初始化超时。该项单独复测仍失败；从 `HEAD=4a19c4b` 导出的只读基线副本运行同一测试也复现，不能归为本轮材料变更回归。排除此项后全库为 **728 passed，3 deselected**（`-k 'not test_circuit_stdio_handshake_and_offline_preview'`）；没有修改该 MCP 测试或用延长超时掩盖问题。
- 本机 Help 的 Dispersion 页明确区分 rad/s 角频率与 1/s 阻尼，HF Overview 将两个旋磁频率定义为 omega_l/omega_m；官方 One-way Transmission Device 为磁 Gyrotropic 的瞬态示例。接口未自动选择 T 求解器。
- 偏置场来源模式仍沿用 CST Reset 默认；未猜测 `SetMagnetostaticDepSourceField` 的 Automatic/Homogeneous 枚举。在已有磁静态场源的工程中，实际来源需原生检查为 Homogeneous field 后才能依赖所给方向。没有执行原生材料读回、rebuild、来源切换、求解或性能测量；`readback_verified=False`、`solver_verified=False`。

## 2026-10-23：完整复数磁导率张量接口（仅离线）

- 新增 `setup.create_material_tensor`，覆盖全部九个复数常量分量，以及实部/虚部分离的 CST 参数与频率表达式；自动转换 `TensorFormulaImag` 所需的负虚部。同步公共协议、类型存根和 `docs/guides/material_tensors.md`。
- `.venv/Scripts/python.exe -m pytest cst_solver/tests/test_material_tensor.py cst_solver/tests/test_material_dispersion.py cst_solver/tests/test_material_color.py cst_solver/tests/test_expressions.py cst_solver/tests/test_failures.py cst_solver/tests/test_environment.py`：**188 passed**。其中新增张量测试 19 项，覆盖九项索引与复数符号、完整表达式保留、颜色、非法矩阵/非有限数/冲突参数及提交前拒绝。`git diff --check` 通过。
- 核对本机 CST 2026 Help：Tensor formula 仅四面体通用频域，不支持 T；原生磁 Gyrotropic/Polder 模型另有官方瞬态示例。计算开销说明为工程推断，无基准数据。
- 未加载 CST、未修改真实工程、未做 rebuild/原生读回/求解或性能测量。参数表达式由 CST 实际解析及重建的行为仍待实机确认；`readback_verified=False`、`solver_verified=False`。

## 2026-10-21：CST Python 后处理模板暂存接口（未执行检查）

- 按本机 CST 2026 帮助新增 `.rtpy` 静态校验和服务目录暂存入口，并接入显式 MCP 工具。模板校验只解析 Python 语法和 `define/evaluate` 入口名，不导入或执行用户代码。
- CST 官方帮助确认 Post-Processing 模板会在求解后执行；当前帮助没有记录通过 `SimulationTask` API 自动添加模板步骤的方法。用户仍需把 `cst_template_library` 加入 CST 库路径，并在 Post-Processing 任务中绑定一次模板。
- 本轮未运行测试、未加载 CST、未打开或修改工程、未做原生读回或求解。模板代码读取 HB 结果的映射、原生绑定及求解后曲线刷新均未验证；不得把暂存成功当成目标图表联动完成。

## 2026-10-20：任务、端口源和非线性模型通用封装（仅离线）

- 扩展瞬态任务的自动/自适应/固定步进、Gear/Adams 算法与阶数、最小步长；新增 `configure_task_ports` 和 `configure_nonlinear_model`，接入 service 的串行 build 路由及两个显式 MCP 工具。
- 相关离线套件 **179 passed，1 deselected**：覆盖配置单位与范围、源文件检查、原生调用顺序、模型稀疏更新、读回不一致、部分失败审计、worker 保存/关闭和 MCP 排队。排除的是既有 stdio 子进程传输检查，本轮没有新增传输协议。
- 检查使用 fake/stub 原生边界；没有连接 CST、打开真实工程、rebuild 或执行求解。新组合接口的实机行为、积分时钟、信号完整参数、SPICE 器件等价、非线性物理指标均未由本轮离线通过证明。原有 `unverified` 判据和历史证据不变。
- 公共协议、使用示例、开发重点和 `skills/cst-circuit/SKILL.md` 已同步；新 skill 格式检查通过。后续按实际工程需要验证，不主动追加专项实机矩阵。

## 2026-10-19：EM 时间控制高层接口（仅离线）

- 新增通用 `setup.configure_em_time_settings(settings)`：非空稀疏字典支持 `stability_factor`（有限数字 `(0,1]`）和 `output_sampling`（every_step/automatic）。纯数据校验先于工程访问；只提交当前 model3d 的历史块，不 Reset、不切换求解器、不重建、不修改 DS 或外部链接、不自动保存或求解。
- service `build / configure_em_time_settings` 和同名 MCP 工具已显式接入唯一 worker，配置后保存；部分提交失败保留请求、原生命令、消息和失败审计。没有三维域时明确拒绝，不回退到 schematic。MCP 电路工具总数为八个。
- 命令语义来自本机 CST 2026 官方 `special_vbasolver_solver_object.htm`：TimeStepStabilityFactor 乘到允许时间步，AutomaticTimeSignalSampling False 表示每个时间步落盘。该来源及既有脚本不构成本次高层组合接口的实机验收。
- 完整离线回归 **642 passed，2 deselected，9 既有 warnings**；包含 MCP stdio 工具列表和普通离线预览，未运行 gui/cst_live。独立只读代码复核未发现阻塞问题。受限进程的握手超时保留日志，以正常本机子进程权限通过回归，没有延长测试时限。
- wheel/sdist 构建、独立目标安装和四包导入通过，未加载 CST SDK；新 EM 模块及两个类型声明均在 wheel 中，两份更新 skill 均在 sdist 中。发行 Python 源码通过 Python 3.9 语法解析，未包含 CST 工程、DLL、锁或 work 产物；两份 skill 格式校验通过。
- 返回 `readback=None/readback_status='unsupported'`，readback、实际积分时钟、每步输出和 solver 验证标志全为 False；没有伪造 getter 或从请求值推导实际 ps。本轮没有启动 CST、实机读回或求解；既有线性/非线性状态不变。
- 日志、来源摘要和制品检查置于 `work/em-time-api/`；使用方法见 [EM 配置指南](guides/circuit_cosimulation.md#em-时间步与每步输出配置)，仓库场路及 simulation skill 已同步。

## 2026-10-19：功能与 skill 优先的离线收尾

- 按用户最新确认，先完成功能和 skill，暂缓追加实机验证；未再启动新的 CST 会话、读回或求解。此前已运行的非线性失败及 SPICE 未验证状态原样保留。
- 新增 `CircuitAPI.configure_transient_task`，覆盖常用瞬态模式、时长、采样、请求积分步长、最大频率和精度；按工程现有单位换算，不改全局单位，不自动求解。实际积分时钟与输出网格仍需运行证据，返回值明确保留未验证标志。
- 服务新增 `build / configure_transient_task`，MCP 显式增加 `configure_circuit_transient_task`，沿用串行 worker、部分失败审计和保存语义。仓库 `cst-circuit` skill 及接口指南同步更新；没有安装全局 skill 或修改公共环境。
- 完整离线回归 **615 passed，2 deselected，9 既有 warnings**，包含 MCP stdio 握手；未运行 `gui` / `cst_live` 测试。新配置组合只取得离线验证，不计为新的 CST 实机验收。独立复核无阻塞问题；skill 格式校验通过。
- 最终 wheel/sdist 构建和 work 内独立目标安装通过；四个包均从新安装目标导入，未加载 CST SDK。wheel 含新配置接口及类型声明，sdist 含场路 skill；全部发行 Python 源码通过 Python 3.9 语法解析，制品不含 CST 工程、原生 DLL、锁或 work 产物。
- 测试日志和本轮制品检查保存在 `work/circuit-validation/20261019-timestep/`。新增功能及后续边界见 [开发重点](CIRCUIT_DEVELOPMENT.md) 和 [接口指南](guides/circuit_cosimulation.md)。

## 2026-10-19：DS 实际时间步及线性瞬态联合复核

- 核心 Python 电路封装仍为 `0.2.0.dev0`；详细内部时间步控制/原生诊断由验证脚本调用 SDK，尚未全部提供为独立高层 API。
- 使用 DS Simulated 保存全部实际时间点、三维保存每个时间步；新日志无 DS 插值警告。23,868 单元同一网格的三档实际 DS/EM 步长一致为 **0.8189415936 / 0.4094707968 / 0.2047353984 ps**。固定 5 ps 请求不作为实际积分证明。
- 三种负载和时间步矩阵的最大参考幅值误差 **0.16671%**、相位误差 **0.19072°**、两侧端口波形 RMS 差 **0.68278%**；时间步变化的最大基波幅值变化 **0.05042%**、相位变化 **0.03357°**、波形 NRMSE **0.07718%**。冻结门槛未放宽。
- 普通网络瞬态原 100 MHz 起始数据用于 DC 的警告保留未验证。另一个同网格副本补算 0–5 GHz，DS 普通瞬态使用 Gear2/800 fs/向量拟合，无警告，公共契约 succeeded；任务执行期间 EM 日志/输出摘要不变。与真实联合稳态最大幅值差 **0.07698%**、相位差 **0.18437°**、NRMSE **0.33059%**。
- 补齐独立三维局部电场：每个端口间隙 32 个内部采样点，按官方定向电压正积分，与该次 DS 电压比较。两个负载使用相同 **40,716 单元诊断网格**，不混入原 23,868 单元时间收敛矩阵。最大幅值差 **0.02129%**、相位差 **0.08690°**、波形 NRMSE **0.15303%**；负载改变后的局部场积分变化与 DS 变化也通过 3% 检查。端点探针在 PEC 上为零的三节点诊断没有通过，没有提升等级。
- 独立只读复核重算原始曲线、场 NPZ 及逐行摘要，接受 V4 物理门槛。界面参考观察仍未验证；既有独立官方教程 SDK 参考没有冒称 UI 构建/执行。V5 非线性开始前的物理门槛已满足，其最终 UI、I–V、KCL、谐波和独立网格/时间收敛仍须另验。
- 窗口修正：只识别完整可读、无按钮且进程/owner 匹配的已知保存进度正文；未知/空/截断正文保持阻塞。读取期间已消失的窗口不作为当前可见阻塞窗口，仍不据此推断 SDK 或 solver 成功。回归 **574 passed，2 deselected，9 既有 warnings**；受控原生消息框 **1 passed**。
- 二极管封装修正通过独立审查：完整十五项实际属性/类型/单位读回，Berkeley 身份标注为原生参数模式证据，模型先写、参数最后读回；保存重开确认 IS=1e-14 A、N=1、RS=1 Ω、CJO=0 F、TT=0。该校准副本内另一个 SPICE 文件链接缺失，因此只计 D1 输入读回通过，不计整个工程可运行或 SPICE 依赖通过。
- 新增二极管/SPICE 身份、单位及执行前后外部文件摘要检查后，正常本机子进程权限下完整离线套件 **593 passed，2 deselected，9 既有 warnings**。此前受限子进程的 MCP 握手超时保留失败日志，没有延长测试超时。wheel/sdist 构建及 work 内隔离安装/普通导入通过，不加载 CST SDK。
- V5 内置二极管 1 V 真实联合已执行；同网格时间步减半和现代 MeshSettings 实际加密到 46,332 单元后，输出基波及二/三次谐波变化均低于原门槛，但 MWS 输出接口电流残差仍约 **1.812% > 1%**，保持 failed。普通网络瞬态同配置对照的接口残差约 1.48e-14，输出 NRMSE 差 0.07370%；不能用对照结果覆盖真实联合失败。手动将 DS 估计最大频率从自动 3.337 GHz 固定为批准范围内的 5 GHz，读数和残差不变。详见 [非线性排查](CIRCUIT_NONLINEAR_REPORT.md)。
- 详细说明见 [时间步报告](CIRCUIT_TIMESTEP_REPORT.md)。原始工程、脚本、JSON/CSV、失败记录和阶段验收存于 `work/circuit-validation/20261019-timestep/`；旧证据目录保留。没有修改全局环境或迁移源，没有推送。

## 2026-10-19：批准几何后的 CST 2026.1 实机阶段（0.2.0.dev0）

- 三维样例按用户已确认的预览建模；原生读回 3 个实体、2 个离散端口，坐标和单位一致，依赖阶段重建并保存。网格 23,868 单元，低于 200,000 上限。
- V1 保存关闭重开一致；V2 RLC 四条复数 S 对解析式最大误差 <3e-15，C=1→2→1 pF 回环和谐振检查通过；独立官方教程 SDK 副本差异 <1.3e-14；纯电路瞬态 RMS 误差 0.0507%。
- V3 两个端口分别实际求解，原生 SUCCESS；25/50/100 Ω 的 DS network 加载与独立矩阵参考最大复数误差 3.12e-9。旧三维运行契约因非空 INFO 返回 failed 的原始记录保留，没有改写其默认口径，三维完成由独立原生状态及两次实际激励日志证明。
- V4 三种负载真实 `cosimulation` 已运行，两侧任务/三维日志和电压/电流时间曲线均取得；稳态最大幅值误差 0.167%、相位误差 0.211°、两侧波形 RMS 差 0.560%。**DS 仍警告 5 ps 输出为插值，固定步长及关闭 auto solver 后提示仍在；严格验收保持 unverified，V5 非线性未启动。** 没有降低门槛或仅凭曲线更新时间宣称双向联合已验收。
- V6 仅同工程固有 EM 块的 network 搬运/重开/重算通过，链接路径均在新副本内，与原曲线差异 0；外部 CST/SPICE 及瞬态搬运仍未验收。V7 的错误模式、缓存、缺失工程和错误引脚实机拒绝测试未提交额外求解；完整中断恢复矩阵未验收。
- 真实 RunService 检查通过：原理图读回、RLC 参数变化后目标任务求解、保存导出均在唯一 worker；重复 request ID 未重复执行。该记录不代表 V4 通过 service/MCP 验收。
- 最终离线回归：**571 passed，2 deselected，9 既有 warnings**；其中包含 MCP stdio 初始化、工具列表及离线预览。受限环境曾出现 stdio 子进程超时，正常本机进程权限重验通过。
- 独立 GUI 自测：**1 passed**，读取受控消息框标题/正文/按钮后关闭测试自身消息框。修复测试的 Windows venv 启动器 PID 与实际窗口进程不一致的问题。实际 CST 窗口只读观察，没有点击 CST 弹窗。
- 显式 opt-in 保存结果读回：**1 passed**，读取搬运副本的 `Tasks\\SP_Load\\S-Parameters\\S2,1`、显式 run 0；该测试本身不证明求解执行。
- wheel/sdist 在 `work/circuit-development/build-env` 的既有隔离构建环境中构建通过；普通 `.venv` 的旧 setuptools 不支持现行 SPDX 许可字段，失败日志保留，没有修改全局环境或降低构建依赖。wheel 在工作目录独立安装/导入通过，四个模块均来自隔离目标，CST SDK 未加载；制品包含新证据模块及类型声明，不包含工程、DLL、会话锁或 work 产物。
- 开发保持 `0.2.0.dev0`，不将尚未通过的 V4/V5 列为正式支持。详细输入、失败尝试、CST build、数值对照、服务/搬运范围见 [实机记录](CIRCUIT_LIVE_REPORT.md)。全部工程和原始证据在忽略目录 `work/circuit-validation/20261019-live/`，迁移源和用户全局配置未改动。

## 2026-10-19：Design Studio 接口离线阶段（0.2.0.dev0）

- 完整非界面、非实机回归：**540 passed，2 deselected，9 既有 warnings**。新增 56 项测试，覆盖单位、端点、目标结果归属、错误/审计、依赖、路径碰撞与 MCP 接入。
- MCP stdio 初始化、工具列表及离线预览调用通过；该测试不连接 CST。
- wheel/sdist 构建与独立目录安装/导入通过，CST SDK 未加载，制品不包含工程/DLL/工作目录产物。
- 仅生成真实参数几何/端口预览。没有创建 CST 工程、rebuild、实机 readback 或求解。
- 原生任务完成证据提取、三维映射与链接重定位仍待实机校准；运行/搬运返回保守的未验证状态，不能报告场路联合仿真已验收。
- 详细证据、已知边界、样例坐标和审阅产物见 [本轮交付记录](CIRCUIT_OFFLINE_REPORT.md)。以下首发版本记录保留其历史含义。

记录 `cst-automation` 0.1.0 拆分实现的离线验证。几何 API 检查、结果读取和真实 CST 求解分开判定。下列本地运行与 GitHub Actions 运行分别记录，不能相互替代。

## 源状态与隔离

- 源仓库：`D:\成电博士生涯\自动建模算法尝试\TPC`，HEAD `51e4a63d302f0deea58d2a2df349892087dbdfe7`，remote `https://github.com/Ding-zhenke/TPC.git`。
- 对源目录执行只读 Git 状态查询时，Git 返回 `fatal: this operation must be run in a work tree`。迁移前把 111 个相关源码、测试、文档和许可证文件复制到目标仓库忽略的 `work/source-snapshot/`，并记录 SHA-256 清单及可读取的 HEAD/remote。无法据此声称源仓库干净；源目录没有被迁移脚本写入或清理。
- 所有测试从本仓库副本执行，并设置 `PYTHONDONTWRITEBYTECODE=1`、`python -B`，pytest 临时文件放在被忽略的 `work/pytest-tmp/`。

## 离线测试

```powershell
$env:TEMP = Join-Path (Get-Location) 'work\pytest-tmp'
$env:TMP = $env:TEMP
$env:PYTHONDONTWRITEBYTECODE = '1'
python -B -m pytest -o addopts='' -m "not gui" -q
```

本次修复后的本地运行：**484 passed, 1 deselected, 9 warnings**。唯一 deselected 项是 `test_native_body_is_reported_while_message_box_is_open`，它通过真实 Win32 消息框和 PowerShell UI Automation 检查桌面可访问性，标记为 `gui`，仅在交互式 Windows 会话中 opt-in 运行：

```powershell
python -B -m pytest -o addopts='' -m gui -q cst_solver/tests/test_dialog_windows.py
```

普通 pytest 默认排除 `gui` 标记，CI 命令也显式排除。离线测试使用 fake backend、stub CST 模块和离线文件；没有打开 CST 或用户工程。9 条警告来自端口 VBA 测试验证未提供 orientation 时的默认朝向提示，不是失败。

## GitHub Actions 故障诊断

- 首次 Actions 运行 [39219977888](https://github.com/Ding-zhenke/cst-automation/actions/runs/39219977888) 中，Python 3.9 核心测试 **481 passed, 1 skipped, 1 failed**。失败是 `test_interface_abi_match_is_reported_offline` 的测试数据重复：在 Python 3.9 上，硬编码 `cp39` 与运行时 ABI 标签相同；被测接口目录只会枚举到一个 `cp39` 文件。修复后的测试显式固定 `cp39` 作为运行时标签，并对发现的接口 ABI 去重后比较；本地回归测试通过。
- 同一运行的 Python 3.11 核心测试为 **481 passed, 1 skipped, 1 failed**。唯一失败是上述真实桌面 UIA 测试在 hosted runner 的 PowerShell bridge 上 4 秒超时。该检查依赖交互式 Windows 桌面，不能作为离线 CI 测试；现在它标记为 `gui` 并从默认测试和 CI 排除，仍可在本地交互式 Windows 会话中显式运行。没有修改生产 UIA 逻辑或放宽其超时。
- 构建和 MCP Actions job 在该次运行成功。该运行的 checkout/setup-python 步骤还报告 Node 20 弃用告警；工作流现改用 `actions/checkout@v7.0.1` 与 `actions/setup-python@v7.0.0`。
- 上述 Actions 结果是修复前的远程证据。本次修改尚未推送，因此没有修复后的 Actions 结果；本地测试不能代替后续远程运行。

## MCP 与技能

- MCP 子套件：`python -B -m pytest cst_mcp/tests -xvv`，此前运行 **31 passed**，使用 MCP Python SDK 1.29.1。项目 extra 声明 `mcp>=1.29,<2` 且限 Python 3.10+，以匹配已测试的 1.x server API；没有完成 stdio/网络传输握手验证。
- 四个 `skills/cst-*` 入口使用 skill-creator 的 `quick_validate.py` 按目录校验；每个入口均通过。

## 发行制品

```powershell
python -B -m build --no-isolation --wheel --sdist
```

结果：构建成功，输出 `dist/cst_automation-0.1.0-py3-none-any.whl` 与 `dist/cst_automation-0.1.0.tar.gz`。setuptools 在当前 Anaconda 环境打印 `bdist_conda` 可选 entry point 导入提示；该提示未阻止制品生成。许可证元数据使用 SPDX 字符串 `MIT`。

wheel 使用本地 `.venv` 安装后，在独立工作目录导入 `cst_solver`、`cst_automation`、`tpc_service` 和 `cst_mcp`。`importlib.util.find_spec` 返回的四个包路径均位于 `.venv/Lib/site-packages/`。该环境继承系统 site-packages 供 NumPy 等依赖使用，但发行包来自刚构建的 wheel。

## 跨仓库接口与证据边界

- 只读检查 `E:\Autocode\TPC\pyproject.toml` 与 `E:\Autocode\em-enclosure\pyproject.toml`：两个目标都声明可选 extra `cst = ["cst-automation>=0.1,<1"]`，与本包首发版本约定一致。
- TPC 和 em-enclosure 的 handler 注册形态与 `RunService.register_handler(kind, handler, *, replace=False)` 相符。TPC 现有 `_guards` 调用点有对应实现；本包现新增稳定公开入口 `cst_solver.guards`，本轮不改写 TPC 源调用点。
- 本轮没有安装并联调相邻仓库，也没有修改它们；因此不报告真实跨包调用通过。
- 没有在 CST Studio Suite 中执行真实几何重建、结果 readback 或求解。fake/mock、导入和制品安装均不构成这些验证。
- GitHub private 仓库 `Ding-zhenke/cst-automation` 已创建，`origin` 指向该仓库；初始提交 `1e00a1f` 已在 `origin/main` 核验。当时补充提交留在本地，后续提交和合并状态以当前 Git 历史为准。


## 2026-10-28 周期稳态射击法配置（离线）

新增 configure_steady_state_task 的纯数据校验、Python facade/adapter、类型声明、
服务 build 路由及 MCP configure_circuit_steady_state_task。原生命令依据为本机
CST 2026 Help 的 transient shooting 模式、steady state period detection/period/tolerance。
离线测试覆盖自动/手动周期、任务局部单位、非法输入预检、任务冲突、部分失败、
原生读回不一致、worker 保存及 MCP 排队；未连接 CST 或启动新求解。
配置读回、实际周期相容性、射击法收敛、源归一化、宽带时域拟合和运行提速分别
验收；当前后五项仍未验证。不把射击法称作电路包络或泵浦 HB 小信号接口。



## 2026-11-03 建模 API 与技能核对（离线）

- 以实际 setup mixin/signature、显式会话白名单及本机官方 CST 2026 VBA Help 核对。
  全量可重复静态清单位于 scripts/audit_modeling_capabilities.py；普通导入未加载 CST SDK。
- 新增聚焦 F 频率/四面体网格设置、混合原生扫描校验与相关会话预检；补齐基础体、
  曲线、布尔、变换、拾取、WCS、材料及端口等明确路由。新设置返回 native readback
  unsupported，readback_verified/mesh_verified/solver_verified 保持 False。
- 回归修复边界 min/max、六边形曲线组、圆环半径转换、缩放因子、端口镜像；新增
  具名实体/曲线项删除。会话执行拒绝只生成命令而不执行的 log_flag，阶段重试按 stage_id 去重。
- 对本轮相关 API/会话回归运行得到 154 passed。全库离线运行得到 1053 passed、
  3 failed、2 deselected；两个失败为 Windows CreateJunction 权限拒绝，一个为
  既有 MCP stdio 初始化响应超时。三项在本机权限下独立复核全部通过；最终完整离线
  复核为 **1061 passed、2 deselected**（41.73 s），未更改测试门槛。实机/GUI 测试未启用。
- 新增网格频率与参数扫描技能，重写建模操作选择和语义参考；代表场景离线演练覆盖
  空心圆柱、非默认曲线组孔洞、实体/端口分别变换、零态加对数材料扫描，以及按电尺寸
  选择少点/Automatic 自适应。技能演练和命令测试均不代替原生几何读回及求解验收。
- 未启动 CST 或执行真实网格/求解，未据此声明当前工程配置已生效或数值收敛。
- 当时用户环境安装的公共插件 0.3.0 包含 11 个入口，构建的相对引用、入口集合与公共内容检查通过；
  已正常安装并核验 enabled，三个本轮重点技能与仓库源码 SHA256 一致。此记录描述当时安装的插件；本仓库当前源清单与技能目录以 `plugin.json` 和 `skills/` 为准。

## 2026-10-27 维护验证

- **Git 来源已恢复**：本机目录原为不含 `.git` 的源码副本。先保存文件快照，再在 `work/maintenance-20261027/upstream/` 克隆完整仓库并恢复根目录 Git 元数据；重建索引时保留全部工作文件。维护前远程 main 为 `07279b078af3484f6f0ad8c0ed6c9ed02db702f5`。该提交的 [Actions 40395424088](https://github.com/Ding-zhenke/cst-automation/actions/runs/40395424088) 已成功；这不是当前维护改动的 CI 结果。
- **维护提交的远程 CI**：分支 `codex/portable-environment-validation` 的提交 `adf187b3fa254554effb7d328fd8e7a71b529538` 已推送；[Actions 40399304203](https://github.com/Ding-zhenke/cst-automation/actions/runs/40399304203) 的 Python 3.9、3.11、MCP 和 build（包含全新环境的 wheel 安装与 stdio 检查）四个 job 全部成功。修复及本记录通过 [草稿 PR #2](https://github.com/Ding-zhenke/cst-automation/pull/2) 提交审阅，未合并到 main。
- **环境与 CLI**：发行包的兼容 `config.py` 不再携带机器路径；离线检查对缺失 SDK 目录、未发现 SDK、选中安装已知 ABI 不匹配报告 `unavailable` 并退出 1。`doctor --json` 已支持，默认仍输出 JSON。测试验证了未配置时发现安装、显式无效路径不回退、JSON 输出、退出码及自定义 SDK 的 ABI 归属。
- **离线回归**：仓库 `.venv`（Python 3.13.9，不继承系统包）执行 `python -B -m pytest -o addopts='' -m "not gui" -q -p no:cacheprovider --basetemp=work/maintenance-20261027/pytest-full`：**490 passed, 1 deselected, 9 warnings**。警告仍为端口默认朝向提示；GUI 用例未运行。
- **SDK 导入**：显式设置 `CST_INSTALL_PATH=E:\CST2026` 后，Python 3.13.9 / CST 2026 的 cp313 匹配，`doctor --probe` 实际导入 `cst.interface` 和 `cst.results` 成功，状态为 `importable`。该路径是本机验证参数，不是发行默认值；不代表许可证、readback 或 solver 已通过。
- **MCP stdio**：新增真实子进程集成测试，使用 MCP Python SDK 1.30.0，完成初始化、9 个工具发现、读写注解、能力调用、未知工具/参数错误、假后端任务排队/状态/结果与关闭工程。测试阻止实际加载 CST，且检查请求 `run_id=7` 能原样返回；同时修复 FakeBackend 固定返回 run ID 0 的问题。通过的是 stdio 与 fake 任务链路，本包没有实现网络传输入口，不声称网络传输通过。
- **发行制品**：构建 wheel 和 sdist 成功；构建后端最低版本改为支持 SPDX license 字符串的 `setuptools>=77`。制品不含 `work/`、`.venv/`、源码备份或 Git 元数据，wheel 内配置无机器路径。
- **干净安装**：`work/maintenance-20261027/release-venv/` 由 `venv` 新建，`include-system-site-packages = false`；安装刚构建的 wheel 及声明的 NumPy/MCP 依赖。独立目录中清除 `PYTHONPATH`，四个包的加载路径均在该环境 `site-packages`，普通导入不改 `sys.path`、不加载 `cst`。曲线调用、缺失 SDK 的 doctor 退出码 1、安装版 stdio 握手/9 个工具发现/结构化错误均通过。可复用检查脚本为 `scripts/verify_wheel.py`；CI 的 build job 也执行该隔离安装检查。
- **尚未验收**：真实 CST 几何重建、实际消息/UIA、S 参数结果树发现、远场导出、solver，以及相邻领域仓库联调。具体几何参数、端口及阶段证据方案见 [真机验收预览](REAL_CST_ACCEPTANCE.md)，等待用户审阅后才构造几何。运行中取消接口仍未开放。
## 2026-11-04 HB 后处理任务与资源审计

- 新增配置专用任务链配置/读回及模板资源三件套审计；38 项相关离线测试通过。
  覆盖父/子类型与关系、同名拒绝、启用和相邻顺序、缺资源、陈旧任务设置、
  资源路径和源码摘要冲突，以及既有源码替换/曲线写入回归。
- 没有进行求解、网格、扫描、模板执行或 Computer Use。空 DS 工程的实机
  验证尝试在 CST DE 启动阶段失败：本机限制拒绝 CST 内部总线 socket，
  未创建工程，未达到任务配置、首次绑定、原生保存或重开验收层级。
- 官方 DS 模板枚举需要运行中的后处理任务；尚无已核实的配置专用首次注册
  入口。资源审计和任务顺序读回不能作为首次绑定认证。本次未新增 bind MCP
  或声称首次注册可用，未提交/发布该未完成能力。

### 同日续作：首次资源注册与归档重开

- 经授权提升本机执行权限后，在本聊天独立空 DS 工程中恢复成功；未操作其他
  会话工程，未使用 Computer Use，未执行 EM/DC/HB、网格、扫描或模板评估。
- 新增版本受限 `register_python_result_template` facade、资源格式编译/审计、
  显式 service/MCP build 路由。原生版本为 `Version 2026.1 - Oct 22 2025`。
- 首次导入后，原生保存关闭，将任务资源目录移出 companion 目录，再重开；
  CST 从 `.cst` 恢复三文件。完整注册描述、源码与元数据摘要、调用方设置和
  HB→Post 启用/顺序均匹配。默认同名与过期摘要拒绝，受完整摘要保护的替换
  同样完成归档重开；所属会话缓存句柄已刷新，并能继续取得登记工程。
- 已知历史有效绑定的配置专用对照也返回空枚举，确认空闲枚举不是有效的
  绑定存在性判据。`registration_persistence_verified/reopen_verified=True`
  仅认证原生归档内容重建；`binding_verified/native_template_enumeration_verified/
  template_execution_verified=False`，不声称模板运行时识别或计算已认证。
- 首次将 P 标志推作 all_runs 的实现已纠正：已知有效参考源码声明 single_run
  但使用相同 P/EP10。检查器模式标为 unknown，保存原始标志，请求声明另记；
  本版仅接受 single_run，并对该模式重新完成首次注册与替换的实机归档重开。
- 相关离线回归 120 项通过，包含资源格式、三文件摘要冲突、非法输入预检、
  既有模板/曲线接口，以及服务/MCP配置路由；fake 不作为实机证据。
- 独立测试工程保留诊断任务与审计资料。可选诊断任务清理的原生 Delete 返回
  Unknown internal error，未重试；随后只读确认目标 single_run 注册摘要及
  HB→Post 链未改变，HB/Post 结果子树为空。该清理不属于注册接口。

## 2026-11-04 EM 频率范围参数引用修复

- `set_frequency_range` / 旧别名 `freq_limit` 的原生频段命令改为带引号的表达式参数，保留 `fmin`、`fmax` 和组合表达式；数值端点保持兼容。语法依据为本机 CST 2026 Python Tutorial 的 Solver Setup。
- 会话 `model_api` 已有显式注册，本次补测位置参数和关键字参数均经过真实封装，未新增跨包协议。新增 10 项回归在修复前全部失败，修复后通过；频率及会话相关 92 项测试通过。
- 全库离线回归最终为 **1133 passed, 2 deselected, 9 warnings**（45.56 s），日志：`work/frequency-range-fix/full-unrestricted.log`。初次受限运行的 `test_staging_rejects_link_redirecting_group_outside_library` 与 `test_template_staging_is_sdk_free_and_stays_in_workdir[True]` 因 Windows 目录链接权限失败；允许测试所需本机权限后均通过。
- 本次仅验证命令生成和会话路由，没有操作真实 CST 工程、读回原生频率参数依赖或执行求解。
