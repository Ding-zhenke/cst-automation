# HF Tet 专项控制

## 曲率

For modern HF Tet mesh curvature, `configure_tetrahedral_mesh.curvature_order`
accepts only strict integers 1, 2, 3; require `hf-tet-curvature-order-v1` on the
actual worker and read [curvature scope and sources](../../../docs/guides/hf_tet_curvature_order.md).
This field is the geometry-curving polynomial order, not FDSolver.OrderTet or
AccuracyTet. Order alone leaves policy untouched. For fixed-order trials explicitly
pair it with `curvature_policy="fixedorder"` and require
`hf-tet-curvature-policy-v1`; the only other supported policy is `automatic`.
The owning session verified that order=2 alone under automatic still produced
effective order=3. Policy tokens now have native-history evidence, but stored
order/policy still do not prove effective order: check actual mesher input and log.
No getter, guessed Off token or optimization-loop cap is added.

## 设置历史

Typed mesh/frequency/parallel/linear settings require actual worker capability
`content-bound-settings-history-v1`. Their history captions include a stable digest
of the complete generated command content, preventing a different sparse setting
from replacing the immediately preceding same-caption block under CST's documented
history rule. Identical content keeps the same caption. This does not repair old
missing history or certify native save/reopen; review the current complete profile
and effective run inputs after recovery. Do not use AddToHistoryNoModelChange for
solver/mesh mutations or upgrade a running worker. See the
[settings history contract](../../../docs/guides/settings_history.md).

## 低频线性控制

For documented general-purpose HF Tet low-frequency controls, use
`configure_fd_linear_solver` with sparse strict booleans
`low_frequency_stabilization` and `allow_float_direct_solver`; require actual
worker capability `hf-tet-lf-controls-v1`. Read [LF control scope](../../../docs/guides/hf_tet_lf_controls.md)
before submitting. Omitted values preserve settings. Neither changes AccuracyTet,
order or solver type unless independently requested. Float Direct permission only
applies when AccuracyTet is worse than 1e-6; do not use IE UseDoublePrecision for
HF Tet or invent Direct defect-correction controls. No dedicated getter is
established: settings readback and effective precision remain unverified.

## 近似阶次与内存

For general-purpose HF tetrahedral calculations, `tet_order` is exactly First,
Second or Third. `mixed_order=True` requires an explicit tet_order in the same
request, interpreted as the maximum: CST may use lower order where appropriate.
Example: `{"solver_type":"Direct","tet_order":"Second","mixed_order":true}`.
False alone disables mixed order without changing the existing order; order alone
preserves the mixed setting. Require `hf-tet-order-controls-v1` on the actual worker.
Use the same settings-only route, preserving geometry, ports, residual and Delta-S
thresholds. Lower order or mixed order is a new numerical trial, not a convergence
certificate or a guarantee of lower peak memory. Prior EM/HB evidence is invalidated.
Verify effective settings, cells/DOF, peak memory, per-excitation residual and Delta-S
from the actual run. An iteration/pass cap or successful configuration cannot pass
these checks. For owned-worker upgrades, follow the explicit owned handoff review
in cst-sessions; never claim a creating worker borrowed its DE.
The owning session reported native mixed-order effect in 0.3.46: for unchanged
initial cell count, DOF decreased versus uniform second order. This is evidence
of changed discretization, not convergence or physical performance. Keep memory
released by closing completed reference tabs separate from order-related savings;
do not infer final peak memory from DOF alone. Scope and numbers are in VALIDATION.md.

## 局部边沿、密度与质量

For contact-edge quality, distinguish local size from density transition and
active-mesher quality optimization. `configure_tetrahedral_mesh.adaptation` supports
`singular_edge_refinement` (strict integer 0..3) together with explicit
`refinement_type="automatic"`, and independently `snap_to_geometry` (boolean).
These issue documented HighFrequencyTet MeshAdaption3D controls, not legacy
quality-optimization commands. Level 0 disables singular-edge refinement; level 3
considers all possible singular conductor edges. Additional refinement may exceed
RefThetaFactor/linear-growth limits. Snap projects new interface nodes onto the
original geometry. Neither guarantees convergence or fixes all low-quality cells.
They do not change adaptation frequencies, pass limits, or enable adaptation unless
those fields are explicitly supplied. Require `hf-tet-adaptation-controls-v1`
from the actual worker; do not interrupt a running job to load it. Native readback
and effective-mesh/solver validation remain separate and unverified by configuration.
Read [the HF Tet controls and upgrade boundary](../../../docs/guides/hf_tet_adaptation_controls.md)
when submitting these fields or arranging a worker upgrade.
The local CST Mesh Object help documents
DelaunayOptimizationLevel (0..5) and DelaunayPropagationFactor for Delaunay;
VolumeOptimization and DensityTransitions (0..1) are Advancing Front controls.
These legacy commands do not establish the active modern HF Tet MeshSettings
group's keys or effectiveness. Do not switch mesher or invent modern keys to
force acceptance. Current typed API has no verified active-group quality setter;
this remains a concrete capability gap, separate from the repaired no-Rebuild route.

The current global tetrahedral density/material setters still use legacy `Mesh`
commands. Their receipt identifies `global_controls_backend="legacy_mesh"` and
warns that effectiveness on a modern active HF Tet group is unverified. Global
`MeshSettings.Set` and local `ItemMeshSettings` use different keys by mesh/group/item
type; do not transfer Hex or LF examples into HF Tet. Inspect the actual active
group/effective mesher input and resulting mesh before claiming a density change.
An unchanged initial cell count is a diagnostic clue, not proof that all refinement
was ineffective. Local Solid limits and adaptive MeshAdaption3D controls need their
own effect evidence. Keep the actual mesh-convergence result separate.
