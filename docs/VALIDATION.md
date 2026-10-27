# 验证记录

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
- GitHub private 仓库 `Ding-zhenke/cst-automation` 已创建，`origin` 指向该仓库；初始提交 `1e00a1f` 已在 `origin/main` 核验。本轮补充提交只在本地创建，不在此会话推送，由主会话统一处理最终 push。
