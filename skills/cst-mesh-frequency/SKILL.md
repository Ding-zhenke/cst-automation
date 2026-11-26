---
name: cst-mesh-frequency
description: Choose or change CST electromagnetic mesh and frequency sampling settings, or diagnose saved mesh inputs, low-quality elements and adaptation or convergence records.
---

# 网格与频率

遵守[完整阅读规则](../README.md#完整阅读规则)。先确认工程、求解器、工况和请求。已有网格告警、mesher 输入或收敛记录从[诊断入口](#诊断已有网格或收敛记录)开始。改动原生设置使用[所属会话](../cst-sessions/SKILL.md)，实际求解按[EM 仿真](../cst-simulation/SKILL.md)执行。

## 选择或修改设置

核对实际几何、材料、单位、频带和已有设置。选择密度、自适应点或计算预算时，按[通用电尺寸与成本估算](references/electrical-size.md#通用电尺寸与成本估算)估算材料或模式波长、局部特征和资源需求。时域 FIT 只需该通用段，按六面体密度、局部尺寸及实际单元数核对网格，稳定性检查看网格加密与时域终止条件。频域任务选择自适应频点时，再读[Automatic 与 Single 自适应](references/electrical-size.md#频域-automatic-与-single-自适应)。评估非线性负载所需频段或将子部件设置用于整机时，再核对[整机成本](references/electrical-size.md#非线性负载与整机成本)。

| 要修改的设置 | 必读章节 |
|---|---|
| 模型频带、频域真实采样、自适应频点或输出轴 | [频率表与网格控制](references/frequency-and-adaptation.md#设置项与频率轴)、[模型频带与采样行](references/frequency-and-adaptation.md#模型频带与采样行) |
| F 四面体局部尺寸、pass 与 Delta-S | [局部网格与自适应预算](references/frequency-and-adaptation.md#局部网格与自适应预算) |
| HF Tet 曲率、低频线性控制、离散阶次或边沿加密 | [HF Tet 控制](references/hf-tet-controls.md)中对应章节 |

提交类型化网格或 F 求解器频率、线性、并行设置前，核对[设置历史与 worker 能力](references/hf-tet-controls.md#设置历史)和[设置提交与读回](references/frequency-and-adaptation.md#设置提交与读回)。只配置或准备服务器工程时，保存并报告提交值、原生读回及缺项，到此结束。

## 诊断已有网格或收敛记录

- 低质量单元告警、坏单元归属或保存的 mesher 输入，按[警告快照与输入核验](references/mesh-warnings.md#低质量单元与已有输入)匹配同一工况和网格代次。
- 检查线性求解残差、网格自适应收敛、pass 上限或输出点数时，按[已有日志的收敛与采样核对](references/mesh-warnings.md#已有日志的收敛与采样核对)读取相应记录。
- 只读诊断以现有证据为终点。报告对应工程、工况、日志或输入及仍缺的数据。更改设置、重新建网格或运行求解按用户请求另行进入相应操作。
