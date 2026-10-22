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
