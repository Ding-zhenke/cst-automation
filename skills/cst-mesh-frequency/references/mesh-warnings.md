# 低质量单元与网格输入核验

## 低质量单元与已有输入

When quality warnings appear, preserve the warning's raw mesh generation before
the next pass overwrites it. Follow [warning snapshots and attribution](../../../docs/guides/reusable_operations.md#告警网格快照与归因):
passive file copies with before/copy/after hashes, then independent element-ID and
quality reconstruction. Valid ID ranges or proximity alone do not establish the
material responsible. Poor elements may lie in background air/substrate far from
the suspected contact; locate first, then propose bounded refinement. Do not change
ports or other protected geometry to diagnose mesh quality without authorization.

Reuse `cst_solver.mesh_input.read_saved_options(path)` for the bounded saved
mesher-input decoder instead of rewriting project-specific readers. Read the
[scope and run-binding rules](../../../docs/guides/reusable_operations.md#冻结读取及有效网格输入).
It returns all attributes and SHA256 without a CST connection; it is not a live
getter. Linear iterations, adaptive passes and quality warnings are different
evidence; no verified modern quality-optimization iteration cap is supplied.
The owning session used the published decoder on fresh run input with order=2
matching log.tet; maintenance checked its saved report (see VALIDATION). This is scoped
decoder/order evidence, not mesh convergence or proof that local RF refinement is sufficient.

## 已有日志的收敛与采样核对

从指定工程、工况和运行的既有日志或导出记录中提取所问字段，记录来源与单位。

- 网格自适应查看每轮单元数或 DOF、Delta-S、目标与实际停止原因。达到 pass 上限时，以最后一轮实测值判断目标是否达到。
- 线性求解查看相应激励的残差和终止状态。宽带采样查看实际求解频点、误差检查和终止记录；单独列出结果显示轴的点数。
- 原始日志或曲线缺项时，报告已取得的数值和对应缺项。普通日志、已导出结果和已保存 mesher 输入可直接从文件读取，无需启动会话、改设置或补算。
