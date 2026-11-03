# 2026-10-19 CST 场路接口实机记录

本页保留首轮实机记录：三维样例已按用户批准的参数建成；当时真实瞬态联合有 DS 插值警告，严格验收保持 **unverified**，未启动非线性。后续复核已通过实际时间步收敛、三种负载、局部电场积分及普通网络瞬态对照；新的无警告线性运行通过 V4 物理门槛，详见 [时间步复核](CIRCUIT_TIMESTEP_REPORT.md)。下述历史失败和未通过结论没有改写为成功。

全部工作副本及原始证据在 `work/circuit-validation/20261019-live/`；该目录被 Git 忽略，不随软件发布。没有修改用户原工程、迁移源或全局配置，没有推送。

## 环境和审批

- CST Studio Suite **2026.1 Release from 2025-10-22 (change 1489198)**；安装位置 `C:/SOFTWARE/CST Studio Suite 2026`。
- 本仓库 `.venv`，Python 3.11.7 / cp311，SDK 加载正常。记录：`environment.json`。相关实际任务取得许可并完成；这不代表全部 CST 功能许可证可用。
- 用户本轮确认几何与端口，并授权继续建模及分阶段实机验证。
- 审批预览 SHA-256：`528280a0d3e3e66025ceb4f2074f84329e7ceb6cd9a26e67b9bcb149b4ccd502`。
- 仅创建本次拥有的独立会话；SDK 访问线程取得实际 PID，监测线程只读取缓存的整数 PID。

## 阶段结果

| 阶段 | 结果 | 主要证据目录/文件 |
|---|---|---|
| V0 | 离线回归、SDK 发现、MCP stdio 检查；最终数量见 VALIDATION | `offline-regression-*.log`、`environment.json` |
| V1 | RLC、端口、探针和任务写入→保存→关闭→重开读回一致 | `v1d/before.json`、`after.json`、`acceptance.json` |
| V2 | SP、独立原生 SDK 参考、纯电路瞬态定量通过 | `v2-sp-c/`、`v2-official-reference/`、`v2-transient/`、`v2-contract-b/` |
| V3 | 几何/端口原生读回、三维双端口求解、25/50/100 Ω 网络加载通过 | `v3-readback/`、`v3-bare-c/`、`v3-network-c/` |
| V4 | 真实联合执行和数值吻合已观察；严格门槛未全部通过 | `v4-summary.json`、`v4-captured-evidence-audit.json`、各 `v4-linear-*/` |
| V5 | 未运行，受 V4 严格验收门槛约束 | 无非线性验收声明 |
| V6 | 同工程固有 EM 块的 network 副本搬运/重开/重算通过；外部 CST/SPICE 及瞬态搬运未验收 | `v6-network-self-b/` |
| V7 | A→B→A 与 4 项实机负向用例通过；完整中断恢复/外部依赖矩阵未验收 | `v2-sp-c/`、`v6-network-self-b/negative-cases.json` |

## 纯电路与独立参考

R=10 Ω、L=10 nH、C=1→2→1 pF，两端口参考 50 Ω，0.1–3 GHz、301 点。四条复数 S 曲线相对解析式的最大误差均低于 **3e-15**。谐振峰落在解析谐振频率的一个采样间隔内；恢复 C 后结果恢复，日志证明执行不是简单缓存假定。

独立参考使用本机官方教程的原生 SDK 命令另建工程，直接设置 nH/pF 局部单位，不调用本包的 schema、NativeAdapter、CircuitAPI 或其导出器。与本包结果最大差异 **1.29e-14**。这是官方教程方式的独立 SDK 副本，没有冒称 UI 手工构建参考。

纯电路瞬态：1 GHz 正弦，峰值 1 V 的 Thevenin 电源，内阻 50 Ω，负载 50 Ω，零初值，时长 40 ns，5 ps 步长/采样。与独立 RLC 状态方程 RK4 积分（≤0.5 ps）比较，输出电压相对 RMS 误差 **0.0507%**，低于 1% 门槛。

公共 `run_checked` 已在 `v2-contract-b` 实测通过指定任务执行、日志更新、输入一致性和保存曲线归属检查。历史 run ID、旧完成日志、相同未知读回及未证实缓存仍不能证明本次成功。run 0 是保存工程的当前别名，不是永久历史编号；CSV、参数记录、摘要和运行 token 分别保留本次证据。

## 三维几何、端口与线性 network

| 实体 | X / mm | Y / mm | Z / mm | 材料 |
|---|---|---|---|---|
| 基板 | −10…10 | −5…5 | 0…0.8 | εr=2.2，无损 |
| 地 | −10…10 | −5…5 | −0.035…0 | PEC |
| 微带 | −10…10 | −1.2…1.2 | 0.8…0.835 | PEC |

P1 为 (−9.5,0,0)→(−9.5,0,0.8)，P2 为 (9.5,0,0)→(9.5,0,0.8)，各 50 Ω。空气盒 X±15、Y±10、Z[−5.035,10.835] mm，六面 open、无额外自动扩展。每个依赖阶段重建、读消息和保存；原生实体数量为 3，两个端口坐标与批准值相同。

实际 CST 图片：`v3-readback/cst-geometry.png`。结构化坐标：`geometry-readback.csv`。本机只读检查脚本使用了 `Model3D._execute_vba_code`，这是此 build 的私有执行入口，未新增到公共接口或 MCP。

0.1–5 GHz，六面体 PBA 网格 **23,868 单元**，20 lines/wavelength、minimum step number 15，4 线程、GPU 关闭。关闭 `ConsiderTwoPortReciprocity` 后两个端口分别实际激励，均有完成日志，原生 `get_solver_run_info()` 为 SUCCESS。旧三维 `run_checked` 因任何非空 INFO 消息而报告 failed，其原始结果保留；本次没有改写该旧接口默认行为，以原生完成状态和两条实际激励日志单独记录三维求解证据。

实际同工程模块为 `MWSSCHEM1`，类型读回 `CST MICROWAVE STUDIO schematic block`，两个连接引脚为 1、2。DS 负载通过外端口参考阻抗 25/50/100 Ω 实现；与三维 S 矩阵独立换算到对应功率波参考阻抗后的四条曲线逐点比较：最大复数误差 **3.12e-9**，最大相位误差 **3.80e-7°**。三维保存频率轴为 float32，和 DS 双精度轴最大差异约 2.33e-7 GHz；参考计算先对实/虚部插值，不放宽 0.02 复数误差和 3° 相位门槛。

## 真实瞬态联合：已取得的证据与未通过项

三种负载均实际运行 `TR_COSIM`，任务读回 `type=transient`、`circuit simulator=cosimulation`。源为 1 GHz、峰值 1 V、2 ns 线性爬升、内阻 50 Ω；ASCII 时间以 SI 秒提供，40 ns 总时长、8001 个 DS 输出点。三维能量提前终止设为 `No Check`。

实机证据包括：

- DS 目标任务新日志与完成时间；三维 `Model.log` 新开始/结束记录及 `output.txt` 中 `Network co-simulation: Task TR_COSIM` 绑定。
- 三维原生求解状态 SUCCESS，求解到指定最大时间，实际 EM 积分步长约 **0.819 ps**。
- 两端各有 `[cosim TR_COSIM]` 的三维电压/电流时域结果，以及 DS EM 引脚探针的电压/电流；方向一致，没有用反号拟合掩盖偏差。
- 20–40 ns 稳态与独立裸线网络参考相比，所有复测中最大幅值误差 **0.167%**、最大相位误差 **0.211°**；两侧波形 RMS 最大差异 **0.560%**。

**仍未通过的严格门槛：** DS 始终警告，5 ps 绘图分辨率比其估计最大仿真步长 44.9548 ps 更小，输出中间值会插值。将 time stepping 设为 fixed、time step 设为 0.005 ns，并在导入后再次设置、关闭 auto solver，读回均能确认这些请求，但没有消除该提示。不能把 8001 个绘图点当作 DS 实际积分步长证明，也没有完成独立时间步收敛。因此公共结果保持 unverified，不宣称 V4 完整通过，不启动其依赖的二极管/SPICE V5。

后续应先校准此 build 的联合时间步控制/原始时间采样，或单独审阅是否接受带明确插值说明的线性验收口径；本轮未降低既定门槛。即使数值吻合，也没有把谐波或曲线更新时间单独作为双向耦合证明。

## 诊断、搬运与接口修正

- 先读取真实窗口的标题、正文、按钮、PID、owner 和 class。观察到的脚本控制窗口、Qt 标题栏装饰、无按钮启动控制器及 `Saving model` 进度，与未知/错误/有按钮的对话框分别识别。没有点击实际 CST 弹窗。一次只读 Computer Use 画面捕获因窗口位于捕获显示器外失败，未据此推断界面成功。
- 修复 SDK `DesignEnvironment.pid()` 方法被当作整数属性的问题；保留属性形式兼容。
- 原生新网络必须先以空名称创建，再重命名；电流探针会将输入连接分成两段，V1 实际为 5 段 net。
- RLC 等固有块不调用其不支持的 GetNumberOfFiles；任务类型大小写规范化；探针方向真实读回；结果使用真实 `Tasks\\<task>\\...` 路径及轴标签单位。
- 三维单位改用官方 SetUnit；离散端口使用 Voltage/Current、明确坐标，不使用无效 Folder 或 VoltageAmplitude/CurrentAmplitude。二极管类型名称按官方 CircuitSemi 修正，未提高非线性验证等级。
- `bundle` 先保存并略过会话锁 Model.lok；其他复制错误继续失败。在第二目录中重开、确认 self EM 文件路径全部落在副本内，再改为 50 Ω 重算，与原 CSV 最大差异 **0**。公共 bundle 仍只报告 staging，不自动将一次特定验收推广到外部工程或瞬态搬运。
- 错误运行模式、未证实缓存、缺失工程、错误引脚均被拒绝；前后任务日志摘要及原理图相同，未提交额外求解。真实 RunService 的检查、RLC 参数改变后目标任务求解及保存导出通过，两个拥有会话均由唯一 worker 操作，重复 request ID 未重复执行，见 `service-live/acceptance.json`。完整服务中断恢复和外部 SPICE 依赖矩阵没有实机验收。

失败尝试及其 partial.cst、消息、异常和窗口记录均保留。`v1/v1b/v1c`、`v3-geometry*` 等早期目录不能与后续通过目录混为一谈；离线/几何/结果读取/实际求解/物理数值对照分别记录。

## 证据使用与限制

默认 pytest 不启动 CST。`tests/live` 仍是显式 opt-in 的已保存曲线读回测试；本轮执行脚本另保存在工作目录，重跑前应选择新的输出目录，防止覆盖证据。最终回归、真实消息框诊断测试、制品构建和本地提交记录见 [VALIDATION](VALIDATION.md)。服务与 MCP 的范围也以该记录为准，不能用离线 stdio 成功推定真实瞬态 MCP 通过。

版本保留 `0.2.0.dev0`；没有将尚未完整通过的 V4/V5 标成正式版支持。
