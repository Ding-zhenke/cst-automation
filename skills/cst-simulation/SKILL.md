---
name: cst-simulation
description: Use when configuring or running CST electromagnetic solvers on a reviewed project, including mesh selection, convergence checks, and run-status verification.
---

# CST EM 仿真

真实操作用 [cst-sessions](../cst-sessions/SKILL.md)。确认工程、批准范围、求解器、频段、端口、边界、网格、输出及资源预算，再启动昂贵任务。配置与执行分开。

- 沿用已接受几何与有效基线；参数、材料、接口、边界或参考面改变后检查矩阵有效性，不给旧结果换标签。
- EM 采样、时域激励、材料有效范围和后续电路混频覆盖分别记录，由任务确定范围与精度。
- 细化真实窄隙、接触和高场区，核对实际 cells/DOF、内存、截面及生成日志。相同离散不构成收敛对照；低频/DC 还查连通、稳定化和拟合。
- 时间步请求、输出采样和实际积分时钟分别验证；提交成功不等于原生读回。
- 用已安装版本的 run_checked 或服务契约，保留保存状态、run identity、原生状态及指定结果来源。返回成功不自动证明数值充分或性能达标。
- 失败先查原始阶段与实际弹窗，不因超时重复启动或静默降低门槛，使用 [cst-diagnostics](../cst-diagnostics/SKILL.md)。

EM 联动用 [cst-circuit](../cst-circuit/SKILL.md)，曲线读取用 [cst-results](../cst-results/SKILL.md)。
