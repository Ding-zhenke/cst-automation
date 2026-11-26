# 频率表、模型频带与网格自适应

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

For FIT hex meshes, legacy `Mesh.LinesPerWavelength` alone may not affect the
modern generator. `set_mesh_auto` and `set_mesh_properties` also write the
requested near-model density via `MeshSettings.SetMeshType "Hex"` and
`Set "StepsPerWaveNear", ...` for FIT aliases. With “Use same setting as near to model”
enabled, CST applies that density to the far region too. The API leaves the
link and any separately configured far value in place. The displayed setting
and the generated mesh have separate evidence.

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
table, especially Adapt. flags, when available and not explicitly waived for the
current run; otherwise record the missing readback as unverified. A zero band
boundary does not prove a DC sample.

Two diagnostic solve frequencies do not imply `output_samples=2`: CST requires
at least three display/evaluation samples. Keep the two Single intervals and
omit output_samples to preserve it, or explicitly choose an integer >=3.
The shared validator rejects invalid display counts before the entire batch runs.

Set a bounded adaptation pass count and Delta-S criterion, plus independent
broadband interpolation error and sample/check budgets as needed.

`adaptation.min_passes` requires a strict integer >=2 (observed CST 2026 range
error); `max_passes` must also be >=2 to permit a valid minimum, and min<=max
when both are supplied. The native MaxPasses lower bound is not independently
verified. For an authorized fixed-mesh diagnostic, disable adaptation explicitly;
do not encode it as min=max=1. This does not relax formal convergence criteria.

Material-only sweeps can change skin depth or field localization; geometry sweeps can require
remeshing. Do not promise cross-case mesh/solution reuse from a generic restart
flag. Use [cst-parameter-study](../../cst-parameter-study/SKILL.md) for scan design.

Configuration receipts currently have native settings readback unsupported and
readback_verified/mesh_verified/solver_verified False. Session rebuild/save does
not turn them into mesh or solver evidence. Report requested settings separately
from checked native flags, actual mesh cells/DOF, convergence and solved results.

For an idle, saved, already-owned project, the separate `inspect` option
`native_solver_status=true` reads only the documented SDK solver name, 3D running
flag and current/last run information; see [status fields and gaps](../../../docs/guides/native_solver_status_readback.md).
It does not read Direct, residual accuracy, per-solid local mesh, adaptation,
active mesh type or the complete sampling table. Never infer those values from
the solver name, history, request, default or a table scan that stopped at a blank.
The old worker must not be restarted to load it; wait for safe owned-session review.

Pure `configure_tetrahedral_mesh` batches, optionally combined with
`configure_fd_linear_solver/configure_fd_frequency/configure_fd_parallelization`,
now check messages and save without a full Rebuild. Require the actual worker's
`mesh-settings-no-rebuild-v1` capability; the earlier solver-settings capability
does not cover mesh batches. Mixed geometry calls still rebuild: keep them separate.
No-rebuild is not a guarantee of native result retention; archive and verify required IDs.


同一工况完成网格自适应后，用该网格进行宽带采样；每个显示或插值频点都重新自适应会重复计算。实际 cells/DOF 只能在已建网格后报告。
