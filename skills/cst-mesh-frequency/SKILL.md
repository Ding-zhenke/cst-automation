---
name: cst-mesh-frequency
description: Use when choosing or changing CST electromagnetic mesh density, local refinement, frequency sampling, or F-solver mesh adaptation points and convergence controls.
---

**完整读取要求：** 必须读完本文件及当前操作要求的引用章节。只读前几十行、搜索摘要或工具输出截断都不算完成；连续补齐缺失内容后才能执行依赖的写入或求解。上下文压缩后若只剩摘要，先重新读取，不能靠用户提醒。

# Mesh and frequency decisions

Use [cst-sessions](../cst-sessions/SKILL.md) for actual project operations and
[cst-simulation](../cst-simulation/SKILL.md) for solving. For server preparation,
configure without local solving. Read actual geometry, units, materials, band, solver and
existing frequency-table rows before choosing settings; inherited automatic
settings alone are not a mesh plan.

## Estimate electrical size before enabling adaptation

Estimate each overall dimension and relevant propagation length in wavelengths
over the band. Start with lambda0=c/f and material wavelength lambda0/n using
the applicable dispersive material or mode index. Record which index is known
or approximated; high-permittivity regions can be electrically much larger than
the free-space estimate. For strongly lossy/dispersive media consider complex
propagation constant and penetration depth instead of a lossless-index shortcut.

Combine electrical extents with thin films, contacts, gaps, ports, curvature and
anticipated global/local mesh density. Use prior cells/DOF and memory/timing if
available; otherwise label the cost estimate provisional. There is no universal
size threshold that makes a mesh adequate or automatic adaptation affordable.

- Electrically large or expensive geometry: usually keep the **Adapt. checkbox
  on the Automatic row off**, and select a few Single rows for adaptation.
  Two or three points covering band edges and a representative interior mode
  or resonance are an initial choice. Adjust for narrow resonances, dispersion,
  port cutoffs and field localization; do not certify a band from a fixed trio.
- Electrically small, affordable geometry: Automatic-row adaptation can be
  appropriate. Explain the electrical-size/cost reason and bound the pass budget.
- Preserve a justified accepted mesh when continuing comparable work. A new
  geometry or field-localizing material state can invalidate its suitability.

Explain the estimate, chosen adaptation frequencies/mode and expected cost
before settings are applied. A choice of a few points is conditional, not a ban
on automatic adaptation and not permission to weaken convergence targets.

For nonlinear downstream use, the highest retained mixing frequency is a data
coverage requirement, not automatically a mesh-adaptation frequency. Before
carrying standalone subcomponent settings into a larger assembly, reassess cost
using the assembly's extent, ports, local features and available memory. Record
adaptation points, pass/growth limits and prior memory/timing in the workflow
checkpoint. Reuse a previously accepted cost-controlled strategy for comparable
iterations; justify any reset to broader adaptation. Reaching a pass cap is not
convergence. Review native memory/disk-solver warnings before proposing a restart;
do not automatically stop a live solve or relax numerical acceptance.

## Separate the controls

| Control | Purpose / API |
|---|---|
| Model band | `set_frequency_range`; preserve parameter references |
| Actual broadband frequency sampling | `configure_fd_frequency` → `sampling_intervals` |
| Mesh-adaptation frequencies | same API → `adaptation_frequencies` (Single, Adapt=True), or explicit interval `adaptation` boolean |
| Display/interpolated result resolution | `output_samples`; a dense curve is not that many independent solves |
| Shared sweep/result axis mode | `output_spacing`; CST applies it to adaptive sampling and output axes |
| Global tetrahedral density, material refinement | `configure_tetrahedral_mesh` |
| Local tetrahedral solid size | same API → `local_solids` |
| Pass/Delta-S refinement convergence | same API → `adaptation` |
| Linear-equation residual | `configure_fem_solver(accuracy=...)`; independent of mesh/Delta-S convergence |
| HF tetrahedral polynomial order | `configure_fd_linear_solver` → `tet_order` and `mixed_order`; changes discretization, not residual/Delta-S acceptance |

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

For a parameter-linked EM model band, define the project parameters first and
call `app.set_frequency_range("fmin", "fmax")` with expression strings. Numeric
Python variables passed as `set_frequency_range(fmin, fmax)` produce fixed
bounds. The existing session `model_api` call is
`{"method": "set_frequency_range", "args": ["fmin", "fmax"]}`; use this wrapper
rather than caller-written `Solver.FrequencyRange` history. Derived expression
strings are supported by the same wrapper. Check the active runtime source
when diagnosing linkage; changing skill text does not update Python code.

A settings-only session batch including `set_frequency_range` checks messages
and saves without full Rebuild when the worker advertises
`model-band-no-rebuild-v1`. A mixed geometry batch still rebuilds. This is an
offline-tested execution route, not proof that native history survived: retain
required data and verify the old and new native run IDs, parameters and curves,
including save/reopen when authorized. The model band is not the F-solver
sampling table or evidence that DC or all retained HB products are covered.

`configure_fd_frequency` interval endpoints and adaptation points currently
accept numeric values only. They do not create parameter references or update
the model band. Recheck those separately configured rows when changing band
parameters; quoted model-band expressions alone do not establish their linkage.

Use focused typed settings and inspect runtime signatures. For F tetrahedral
mesh, do not substitute hexahedral `LinesPerWavelength`, arbitrary MeshSettings
keys or old MeshShapes region wrappers. Refine actual high-field gaps, contacts,
ports and thin active regions locally; do not size the entire device by its
smallest feature. Model ideal PEC, finite-conductivity skin depth and thin-sheet
representations according to the intended physics and solver support.

For large-model few-point adaptation, submit an Automatic interval with
`adaptation=False` plus the selected `adaptation_frequencies`. For affordable
automatic adaptation, explicitly set the Automatic interval `adaptation=True`.
Each interval requires start/stop/spacing/samples; spacing is
automatic/linear/logarithmic/single. Automatic samples may be None; range
sampling uses endpoint-inclusive counts. Frequencies use project frequency
units; local mesh max_step uses project length units.

Intervals append by default. To replace inherited user-defined rows, explicitly
use `replace_intervals=True` and provide the complete intended interval/point
set. This resets sample intervals only; it is not a full solver reset, nor proof
that monitor-derived rows are removed. Inspect the resulting native frequency
table, especially Adapt. flags. A zero band boundary does not prove a DC sample.

Set a bounded adaptation pass count and Delta-S criterion, plus independent
broadband interpolation error and sample/check budgets as needed. Material-only
sweeps can change skin depth or field localization; geometry sweeps can require
remeshing. Do not promise cross-case mesh/solution reuse from a generic restart
flag. Use [cst-parameter-study](../cst-parameter-study/SKILL.md) for scan design.

Configuration receipts currently have native settings readback unsupported and
readback_verified/mesh_verified/solver_verified False. Session rebuild/save does
not turn them into mesh or solver evidence. Report requested settings separately
from checked native flags, actual mesh cells/DOF, convergence and solved results.

Pure `configure_tetrahedral_mesh` batches, optionally combined with
`configure_fd_linear_solver/configure_fd_frequency/configure_fd_parallelization`,
now check messages and save without a full Rebuild. Require the actual worker's
`mesh-settings-no-rebuild-v1` capability; the earlier solver-settings capability
does not cover mesh batches. Mixed geometry calls still rebuild: keep them separate.
No-rebuild is not a guarantee of native result retention; archive and verify required IDs.

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
Read [the HF Tet controls and upgrade boundary](../../docs/guides/hf_tet_adaptation_controls.md)
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
