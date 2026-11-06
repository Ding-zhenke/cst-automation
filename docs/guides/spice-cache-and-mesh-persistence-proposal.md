# SPICE 缓存身份与局部网格持久化：离线 API 方案

2026-11-03。依据来源会话的本机只读报告、本仓库源码及本机官方 Block 帮助整理。
本会话未连接 CST、打开工程/结果或读取具体器件证据文件，未启动求解、改运行代码或部署。
具体模型卡、局部组名、物理设置和结果数值不纳入通用包。
下列字段和流程是待实现方案，不是当前 API 已有保证。

## 1. SPICE 的 GetFile 不能按 SetFile 原路径验收

来源会话已核实：SPICE `Block.GetFile()` 返回工程内部 Model/DS/Block 层级下的模型卡缓存，
不是原 SetFile 输入路径；各实例缓存的内容哈希与批准的原模型卡一致。
因此路径不同本身不能作为源模型错误或模型卡内容改变的证据。

本机官方位置：`Online Help/mergedProjects/VBA_DES/special_vbacommands/blockobject.htm`，
`SetCacheFiles(bool bFlag)` 段明确仅适用于 Touchstone file block。不能将它套到 SPICE，
也不能为追求原路径相等擅自更换缓存策略或重导入模型。

### 当时发现的实现缺口及后续状态

`cst_solver/circuit/configuration.py` 的 `configure_nonlinear_model` 中，在读回 SPICE 模型后，
用 `Path(actual['file']).resolve() != Path(settings['file'])` 判定 Native SPICE file/model mismatch。
该断言不能接受内容正确但位于工程内部缓存的 SPICE block；相对缓存路径也不能默认按 Python
当前工作目录解析。此为当时的验收语义缺口，不等于已经发现 CST 内部缓存缺陷。
后续仓库已修改这一验收路径：请求源与实际缓存使用内容证据比较，具体能力和限制以
[公开 API 中的 SPICE 缓存身份核验](../PUBLIC_API.md)为准；以下方案保留为历史设计记录，
不能视为当前实现或实机验收的完整描述。

### 建议的验收合同

分别保留 requested_source_path、native_file_reference 原文、经明确工程目录解析的
resolved_cache_path、block 标识/归属、读取状态及原始错误；不覆盖成一个含义不清的 file 字段。

验收维度独立记录：

- 内容：批准源文件快照与实际缓存的 SHA-256、文件大小、读取时点和可读状态；哈希不同为
  content_mismatch，读不到为 unknown，不回退读取原文件来冒充缓存已验证。
- 模型：实际选中的 SPICE model/subcircuit 名、方言、端口名称/顺序/连接和极性，与批准定义比对。
  同一文件可有多个模型；顶层文件哈希一致不证明模型选择或引脚映射正确。
- 归属：缓存位于当前工程依赖闭包，并绑定当前 block/实例及保存/复制后的工程身份。
  明确解析基准，保留无法确认的归属状态；不能仅看文件名相同或路径含 Block 就算通过。
- 依赖：有 include 等外部依赖时，按可支持的依赖闭包分别记录内容；无法可靠解析的部分保留
  unknown，不把顶层模型卡哈希提升为所有依赖和原生仿真语义均已验证。

path_equal 可作为诊断字段，但不是 SPICE 成功条件。source_content_verified、
pin_mapping_verified、cache_ownership_verified、saved_reopen_verified 分开，
均不能单独提升 solver_verified。任何内容读取均须在授权的稳定保存副本上进行。

## 2. 网格缓存可读不证明局部组已持久化

来源会话重新核对两个候选副本：前一副本 ModelHistory 有三组批准的局部网格配置，
后一副本 ModelHistory 无这三组、对应原生 Size 读回为零，其他旧组仍存在；
后一副本的网格缓存仍可读。这些证据表明两副本的持久化配置不一致。
保存、复制或重建流程失效的根本原因仍未确认，不能宣称已定位 CST 内部 bug。
后续正式副本恢复验证的结果见下段，不能用其倒推两个早先副本不一致的根因。

### 后续来源证据：即时零值不等于永久丢失

来源会话补齐三组并 Mesh.Update 后，同一会话的即时 Get(Size) 均为零；关闭重开后，
原长组名已能正确读回批准值。短名对照发生在长名已经读回正确之后：保持成员和尺寸的
短名映射保存重开也正确，物理实体和端口几何未改变。

因此“组名超过某一长度导致问题”的假设不成立，不新增长度截断规则、不强制改短名，
也不将短名对照称为已证明的根因修复。应保留 before/immediate/reopened 三阶段全表；
不能以生成后即时零值单独判定约束永久丢失。CST 内部上下文或刷新机制仍未确认。

这与前一候选副本历史中确实无组是两类证据，不能合并为同一故障。新阶段已报告的是
生成完成和目标组保存重开后值读回一致，不证明每个实际网格单元满足某项局部尺寸上限，
也不是 RF 网格收敛或器件验收。来源会话明确本阶段没有提交 RF EM/DC/HB。

### 建议的配置快照与保存重开合同

保留 approved_expected；在生成前、生成后即时、保存重开后三个阶段分别记录 native/history：

1. 工程及副本身份、配置阶段/时间、组列表、成员实体标识、网格类型、设置键、原始表达式、
   数值/单位、默认或继承标志、原生查询状态；另存历史是否包含该组的证据。
2. 对每组记录 enumerated_present、exists_in_history、native_value、query_state、matches_expected。
   单独 Size=0 可能涉及默认/继承/查询失败，不能单独等同“组不存在”；结合实际枚举、历史及
   批准的期望值判断。异常、缺组和零值不能都压成一个默认零。即时值不一致时先记为
   needs_reopen_verification；保存重开后符合预期则记 reopen_consistent，保留即时差异，
   不声称刷新机制已定位。重开后仍不符再报告持久化验收失败，不自动重建补救。
3. 保存 API 返回、实际文件写出、复制依赖闭包、关闭重开后配置一致性分别记录。
   保存返回成功不替代重开读回；复制完成不替代目标副本读回。
4. 将 mesh_cache_present/mesh_cache_readable 与 configuration_persisted/matches_expected 分开。
   若无法绑定缓存到本次配置、历史、mesh pass 和运行身份，mesh_matches_configuration=unknown。
   旧缓存可读不能抵消缺失配置，也不能据缓存存在恢复“已保存”结论。

只读诊断不能通过 `ItemMeshSettings` 等上下文变更调用猜测 getter；需按实际接口证据确定
安全读回方式，或明确记录上下文变更风险。检查失败保留现场，不自动补组、重放历史、
更新网格或复算。补齐配置/重建属于来源任务已批准的操作，不授权本会话执行。

### ItemMeshSettings 的语言边界

来源会话实测 VBA 表达式 `ok = MeshSettings.ItemMeshSettings(...)` 报 10091；原先在
`With MeshSettings` 中使用 `.ItemMeshSettings(...)` 的已验证调用形式可配合读回。
Python 侧观察到 bool，不能据此认定 VBA DSL 支持该方法作为可赋值函数。
两种调用形式及错误需分别记录；不能自动把语句改成赋值表达式来探测成功，
不能推断 bool 就是完整 native 配置读回，也不能推断其作用无副作用。

## 3. 低频完整矩阵与 RF 网格独立

来源会话报告最新低频诊断已覆盖全部预期端口及完整复数矩阵，并满足用户明确的残差门槛；
它更新了先前“仅部分端口”的状态。本会话没有独立复测，不复制具体矩阵或结果数值。
这项证据不证明 RF 自适应网格 Delta S 通过，不验证其他频率、工况或偏置下的性能。

后续诊断合同须同时保留：实际频率/单位、预期与完成激励端口集合、矩阵条目集合、
复数值来源/run、每端口残差及门槛、native 完成状态；与 RF mesh pass、Delta S、目标值和
停止原因独立。不能把低频 residual_passed 回填为 RF mesh_converged。

## 4. 拟新增离线回归（未实施）

- 原路径与内部缓存路径不同但内容/模型/端口/归属均正确，不再因路径不同判 mismatch；
  原路径相同但内容变动仍失败；缓存不可读保持 unknown；不调用 SetCacheFiles。
- 缓存相对路径按显式工程目录解析，不依赖进程 cwd；跨副本/跨 block 的错误归属可检出。
- 内容相同但模型或 pin 顺序不符仍失败；多模型和未解析依赖的证据不越级。
- 保存前有组、重开后无组，虽缓存可读仍不通过持久化验收；缺组/零值/默认/查询异常分开。
- 生成后即时零值、重开后批准值：保留阶段差异，不判永久丢失；长名已正确时的短名对照
  不作为长度根因证据；不强制截断名称。VBA 生成不得由 Python bool 推导出赋值式调用。
- 两副本历史不同保留差异，不自动归因为内部 bug；不以只读检查触发补组或 Mesh.Update。
- 完整低频矩阵/残差通过与 RF Delta S 未通过可同时存在；端口缺项不能靠旧缓存补齐。

实施前须先更新 PUBLIC_API，明确版本兼容和可诊断失败字段，再编写替身/临时文件测试。
本次未修改上述路径断言，也未新增或宣称已通过这些测试。
