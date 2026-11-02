---
name: cst-results
description: Use when reading or exporting CST result trees, complex curves, fields, or archived parameter-study cases while preserving units and source run identity.
---

# CST 结果读取

在线读回经过 [cst-sessions](../cst-sessions/SKILL.md)所属工程；离线 Result 文件读取不需要 DE。保存工程和显式运行身份仍须明确。

先列实际树路径及 run ID，再用 cst_solver.Result、CircuitResult 或当前版本相应 API。记录参数、坐标、单位、归一化及复数约定；缺结果保留错误，不代入零、空曲线或旧运行。

当前 run 0 是可变别名，参数研究历史用 cst_solver.circuit.StudyResult(batch_path) 的固定快照。筛选、比较及保存读回遵循[参数研究合同](../cst-circuit/references/parameter-studies.md)。保留 .cst 和结果目录；saved_readback_verified 与真正重开的 reopen_verified 分开报告。

区分输入扫频、一次激励的频谱、时间、参数及运行编号。复幅度用幅值 dB，功率用功率 dB，不对已有 dB 再取对数；相位展开保留共同参考及弱信号掩码。

阈值样点分段和采样谐振复用 cst_automation.curves 的现有规则，不另造判据或把插值认证为连续带宽。图形用 [cst-figures](../cst-figures/SKILL.md)，指标用 [cst-device-characterization](../cst-device-characterization/SKILL.md)。读到结果不证明本轮求解、收敛或性能达标。
