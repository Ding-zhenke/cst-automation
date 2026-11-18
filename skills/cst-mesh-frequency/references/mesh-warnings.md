# 低质量单元与网格输入核验

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
