# `cst_solver` API and workflow

`cst_solver` is the general CST Studio Suite automation layer. It wraps CST's Python/VBA interface for reusable model operations, session handling, solver configuration, saved-result access, and diagnostics. Its import name remains stable for existing Python scripts.

## Capability map

| Area | Modules and entry points |
|---|---|
| Session and project files | `setup`, `ProjectMixin`, save/open/close and session attachment |
| Geometry | `modeling.primitives`, `curves`, `curves_ops`, `booleans`, `transforms`, `picks`, `wcs` |
| Materials and components | `material.MaterialMixin` |
| Simulation setup | `simulation.ports`, `sources`, `monitors`, `boundary`, `solver`; `mesh.MeshMixin` |
| Import/export | `import_export.IOMixin`; field, pattern, and result export mixins |
| Results | `Result` / `result` in `_result_core`; S-parameter and 1D/2D/3D tree readers |
| Safety and diagnostics | `guards` (public), `expressions`, `failures`, `run_contract`, `environment`, `dialogs` |

Importing the package does not open a project, load a CST DLL, modify `sys.path`, or require CST to be installed. The first real CST operation loads the selected installation through `cst_solver.environment`. The `cst` module is supplied by CST Studio Suite and is not a PyPI dependency.

## Installation and environment

Install this project with `python -m pip install cst-automation`. Run `python -m cst_solver doctor --json` to inspect installation discovery, configuration source, Python ABI, and SDK import status. Configure `CST_INSTALL_PATH`, `CST_PYTHON_LIB`, or `CST_MATERIAL_LIB` only when automatic discovery does not find the local installation. See [environment setup](../guides/cst_environment.md) for precedence and error examples.

An ABI match is an offline compatibility clue; it does not prove DLL loading, project readback, or solver success. Preserve the complete diagnostic output when reporting an installation error.

## Session usage

```python
from cst_solver import setup

app = setup(r"D:\Projects\example.cst")
try:
    # Use app methods for materials, solids, ports, boundaries, mesh, and solver setup.
    app.save()
finally:
    app.close()
```

For geometry changes, first derive a preview from the actual parameters and get the user's review. Keep units, work coordinate system, component, material, and port direction explicit. Use `log_flag=0` only to compose history text; generated text has not been applied until submitted through the normal API.

Keep changes in dependency order. After construction, use the project validation/rebuild path and record messages, entity counts, and output files. A clean rebuild verifies geometry state only.

## Simulation and evidence

`app.create_material_tensor(name, epsilon, mu_tensor, *, mu_imag=None, color=None, colour=None)` creates a full complex relative-permeability tensor using CST's Tensor formula material. Numeric complex entries and separate real/imaginary frequency-expression matrices are supported. CST 2026 limits this material to the general purpose frequency domain solver with tetrahedral mesh; it is **not supported by the T/Transient solver**. The native Gyrotropic ferrite model offers a separate, restricted Polder-tensor route for transient work. See [tensor materials](../guides/material_tensors.md) for examples, parameter units, the negative-imaginary sign conversion, and solver/evidence limits.

`app.create_material_gyrotropic(name, epsilon, *, larmor_omega, gyrotropic_omega, damping, bias_direction=(0,0,1), mu_infinity=1, kappa=0, color=None, colour=None)` wraps the native magnetic Gyrotropic model using SI inputs. Both omega inputs are angular frequencies in rad/s (use `2*pi*f_hz` from Hz), direction is a unit vector, and all physical inputs accept CST parameter-expression strings. Numeric ranges and unit directions are checked before project access. It submits material history only, without running a solver. Bias-source selection retains CST's reset default and requires native inspection in projects with magnetostatic sources; see [the SI interface and limits](../guides/material_tensors.md#原生-si-接口与-cst-参数).

`setup.run()` retains its legacy behavior. `setup.run_checked(...)` returns a structured run contract and distinguishes submission, message checks, result presence, and result identity. Save completed results before reading them. Do not report a successful solve unless the run contract status says `succeeded`; record its run token/ID and relevant diagnostics.

For a solver stall, inspect [the actual CST dialog](../guides/cst_dialogs.md), including title, body, buttons, process, and PID. A closed dialog or a returned SDK call does not by itself prove solver success.

## Result access

Use `Result(project_path)` or the backward-compatible `result(project_path)` class for existing saved results. Pass explicit tree paths and run IDs where applicable. S-parameter amplitude convention and run identity are available from `cst_solver.run_contract.result_conventions()`.

Missing result items and read failures remain explicit errors; do not substitute empty data or an older run. Result readback demonstrates data extraction, not that the current session ran the solver or that the design meets a performance target.

Shared band/resonance criteria are implemented once in `cst_automation.curves`. Use that module for CSV or array analysis instead of adding a second threshold implementation to a domain package.

## Service integration

`app.configure_em_time_settings(settings)` configures current-project EM transient stability factor and time-signal output sampling without resetting or running the solver. Sparse keys are `stability_factor` (finite numeric `(0,1]`) and `output_sampling` (`every_step`/`automatic`); Python callers save explicitly. Native readback is unsupported, and actual timestep/output verification remains False. The opt-in circuit service/MCP route of the same name queues configuration and save on the single worker. See [the time-control guide](../guides/circuit_cosimulation.md#em-时间步与每步输出配置) for examples and evidence limits.

`tpc_service` serializes task execution, persists status/events, constrains artifacts to its work directory, and records dialog diagnostics. `CstBackend` solves existing project files. Domain-specific build and study workflows register handlers through `RunService.register_handler`; this package does not import a domain modeler. See [the public service API](../PUBLIC_API.md) for signatures and lifecycle behavior.

## Extension rules

- Add stable CST primitive operations to the existing focused mixin; keep public import names and aliases compatible.
- Update `setup.pyi` and `simulation/setup.pyi` when their public methods change, and add behavior-level offline tests.
- Keep optional CST access lazy. Do not vendor CST modules or add `cst` to package dependencies.
- Keep offline/mock evidence separate from real project readback and solver evidence.

## Basic shapes and parameter sampling

Use the existing Python methods before writing native commands. Their native
history is an implementation detail, not a reason to bypass the API.

| Shape | Existing setup API |
|---|---|
| Brick | `square(xmin, xmax, ymin, ymax, zmin, zmax, name, component, material)`; alias `create_brick` |
| Solid or hollow cylinder | `cylinder(center, r, h, name, axis='z', component='component1', material='PEC')`; alias `create_cylinder` |
| Sphere | `create_sphere(center, radius, name, component='component1', material='PEC')` |
| Cone | `create_cone(bottom_radius, top_radius, height, name, center=None, axis='z', component='component1', material='PEC')` |
| Torus | `create_torus(major_radius, minor_radius, name, center=None, axis='z', component='component1', material='PEC')` |

For cylinders, `r=[outer_radius, inner_radius]`, `h=[axis_min, axis_max]`,
and `center` is the two coordinates perpendicular to the selected axis. Use
CST parameter-expression strings for dimensions that must remain parametric.
These basic methods are explicitly available through session `model_api`.

Parameter sweep configuration supports native linear, logarithmic and explicit
point-list axes. For example, on the session-owned application:

```python
app.configure_sweep('dimensions', {
    'length': {'mode': 'linear', 'start': 1, 'stop': 3, 'samples': 5},
    'scale': {'mode': 'logarithmic', 'start': 1, 'stop': 100, 'samples': 3},
    'state': [0, 1],
})
```

The same mapping is accepted by session `configure_sweep`, together with
`project_id` and stable `stage_id`. Range descriptors retain their CST-native
sampling mode; they are not expanded into arbitrary points. Counts include both
endpoints. A logarithmic range cannot include zero: use a separate discrete
zero-state sequence when required. Configuration does not start a solver.

## Modeling workflow and focused F controls

The maintained [modeling skill](../../skills/cst-modeling/SKILL.md) routes to an
[operation map](../../skills/cst-modeling/references/api-selection.md) and
[geometry/material/port semantics](../../skills/cst-modeling/references/model-operations.md).
They distinguish existing wrappers, explicit session routes and unsupported
native effects. `scripts/audit_modeling_capabilities.py --output work/api-audit`
generates the full current setup signature/source/route inventory without CST.

`configure_fd_frequency(settings)` separates broadband intervals, mesh-adaptation
frequencies and interpolated output resolution. Interval fields are start, stop,
spacing, samples and optional boolean adaptation (False by default). Explicit
`replace_intervals=True` replaces interval definitions; otherwise they append.
`adaptation_frequencies` adds Single rows with adaptation True. Automatic-row
adaptation is selectable: estimate electrical size and mesh cost first, using
few-point adaptation for expensive problems and automatic adaptation when
appropriate for affordable ones. See [mesh/frequency selection](../../skills/cst-mesh-frequency/SKILL.md).

`configure_tetrahedral_mesh(settings)` uses documented global tetrahedral density,
local per-solid edge constraints and bounded pass/Delta-S refinement controls.
It replaces use of hexahedral density and legacy speculative MeshShapes controls
for F tetrahedral work. Both methods preflight without SDK access, submit focused
commands, and return unverified native settings/mesh/solver flags. Python callers
rebuild/save explicitly; persistent sessions perform their usual checkpoint.
See the [public schemas](../PUBLIC_API.md#typed-frequency-domain-sampling-and-tetrahedral-mesh-configuration).

Basic modeling audit corrections include matching boundary faces, passing a
nondefault curve group to hexagonal profiles, translating torus major/minor
radii to native outer/inner extents, actually submitting scale factors, and
using correct port names/destination rules for mirror. `delete_solid` and
`delete_curve_item` provide focused object removal. Session `model_api` explicitly
registers geometry operations and rejects nonexecuting log_flag modes; native
shape and material readback remain independent checks.
