# 原生求解状态读取与设置缺口

本页记录 CST 2026 本机官方帮助和仓库实现的核对。维护侧只做源码和离线测试；
未连接工程、启动网格/求解或验证真实 SDK 返回。工程侧须在所属 worker、工程
和 SDK 线程内进行独立验收。当前运行中的 worker 不因安装新版而自动加载新代码。

| 字段 | 依据与小范围成本 | 当前实现与证据边界 |
|---|---|---|
| 活动求解器名称 | 官方 `cst.interface.Model3D.get_active_solver_name(timeout)`；低成本、一个 SDK getter | `native_solver_status` 逐字段返回原文；名称不能证明 Direct/迭代算法。 |
| 3D solver 是否运行 | 官方 `Model3D.is_solver_running(timeout)`；低成本 | 严格接受 bool；False 不认证 DS、后处理或整个工程空闲。 |
| 当前或最近一次求解信息 | 官方 `Model3D.get_solver_run_info(timeout)`；低成本 | 原生字典逐项保留；不能自行认定属于本轮任务，不能仅凭它证明求解完成或数值通过。 |
| 活动网格类型 | VBA `Mesh.GetActiveMeshType` 有文档，官方 Python SDK 页面未发现同名 getter | 未开放或猜测 Python 方法；若需使用内部只读桥，须另证实项目绑定、执行接口和原生回执。它也不证明实际网格质量。 |
| Direct / 残差精度 | `FDSolver.Type`、`AccuracyTet` 有 setter；未找到本机已验证 getter 或数据库键 | 不从请求、历史或 solver 名称推断当前值。准确映射需要版本证据及独立项目实机核验，成本尚不能可靠估算。 |
| 每实体局部网格 | `Solid.SetMeshStepwidthTet` 是 setter；未找到完整 getter | 不把历史命令当实际内存状态；需确定逐实体读取与对象身份，成本取决于官方支持。 |
| 自适应设置 | 已找到 setter，未找到覆盖本轮字段的 getter | 不推断当前值或用上次求解作为设置快照；需先确认字段映射。 |
| 完整频率采样表 | `AddSampleInterval` 是 setter；尚无已验证行数、逐行键与终止规则 | 不枚举猜测数据库键、不把空值当表结束；缺完整覆盖证据时标记 unsupported，不声称表读完。 |

通用 `GetDataBaseValue` / `GetDataBaseArrayValue` 只证明数据库查询方法存在；
当前没有经验证的上述字段键、行数和结束语义，因此未暴露任意键探测。
`Model.prj`、`simulationproperties.docstore`、保存历史、请求和默认值均不构成
已验收的当前内存状态读回。

所属会话调用 `inspect`，参数示意：

```json
{"project_id":"PROJECT_ID", "native_readback":true, "native_solver_status":true,
 "read_only_review":true, "confirm_idle":true, "expected_digest":"SAVED_SHA256"}
```

该调用须先确认实际所属工程空闲、保存摘要一致且 worker 已广告
`native-solver-status-v1`；提交接口不会启动新 worker，缺能力或句柄时拒绝，
不会 attach。每个 getter 分别给出来源、项目/对象、开始和结束时间、status、
raw、value、error。空返回、无效类型、异常、方法缺失分别保留；不支持的
五类设置与网格类型逐项列出。整体 `readback_verified=false`、
`whole_sequence_idle=unknown`，不将部分查询成功提升成完整设置验收。

运行中的工程如果尚未证明空闲，不能声称满足 `confirm_idle`；保留现场并由
所属会话按受控交接流程在安全空闲后加载/验收。插件只是说明，不安装运行库或
热更新既有 worker。原生 acceptance 应检查每个 getter 的实际返回、工程身份及
异常行为，并单独保留结论；不得为验收触发新求解。
