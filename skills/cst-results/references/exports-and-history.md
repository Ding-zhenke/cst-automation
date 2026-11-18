# Export and retention of saved results

## Install Touchstone Export in the CST project

Use the category and display name from CST's **Result Templates** library.
In these examples, `app` owns the saved, idle project. Registration saves,
closes and reopens that project. Reacquire any cached native handles from
`app.cst_file` afterward.

**3D (MWS).** With no `post_task`, the step is added to the project's
Result Templates list. This example requests 37 complex samples in RI format
at 50 Ω for export after a solver run.

```python
receipt = app.add_builtin_result_template(
    "S-Parameters", "Touchstone Export",
    settings={"NumberOfSamples": 37, "FormatG": "RI", "ReferenceImpedance": 50},
)
```

`FormatG` accepts MA, RI or DB. Use `LimitFreqRange=True` with `FMin` and
`FMax` to restrict the export band. For a second instance, supply a unique
`result_name`; reusing the name raises an error.

**Design Studio.** For an existing SP task named `StaticSP` in the sequence
`SPAndExport`, create a sibling Post task and bind the template to the SP data.
Use task paths relative to the native Tasks root.

```python
receipt = app.add_builtin_result_template(
    "S-Parameters", "Touchstone Export",
    post_task=r"SPAndExport\ExportPost", create_post_task=True,
    settings={"TaskName": r"SPAndExport\StaticSP", "ReferenceImpedance": 50},
)
```

Omit `create_post_task=True` when appending to an existing Post task. DS
accepts `TaskName` and `ReferenceImpedance`. To export on each sequence
update, check the native order is **StaticSP → ExportPost**. Running the Post
task alone can export the source task's saved S-parameters.

Check `registration_persistence_verified` and `reopen_verified` in the receipt.
`template_execution_verified` is false at registration. When execution is
requested, verify the newly written `.sNp` from CST against the intended
source, frequency grid, port order, format and reference impedance.

The tested template is the installed VBA `.rtp` in CST 2026.1 (20251022).
For other templates, use their native setting keys and see the
[API contract](../../../docs/PUBLIC_API.md#add-an-installed-cst-result-template)
for tree references and dynamic result types. With a managed session, use
the `add_builtin_result_template` circuit build operation or its opt-in MCP
tool on a worker advertising `builtin-result-template-v1`.

## Exporting EM sweep points as Touchstone files

For an already saved parameter sweep, use
`Result(project_path).export_touchstone_sweep(output_dir, *, port_count,
reference_ohm, frequency_unit, parameter_names=None)`. It enumerates positive Run IDs
from the main `S1,1` result, reads every `Sij` complex curve for each ID, and reads the
native stored parameter combination. It writes one `run_<id>.sNp` per point plus a
manifest with parameters, axes, normalization metadata and SHA-256 values.

Before calling, confirm the port count/order, frequency-axis unit and the exact real
reference impedance used by the native S data. The writer does not renormalize. It
rejects missing matrix elements, mismatched axes or Run IDs, missing requested parameters,
unit-label conflicts and incomplete native parameter identity. It never falls back to
Run 0, and it refuses an existing output directory so an earlier export cannot be replaced.
The operation only reads saved results; it does not configure or start an EM sweep, connect
to CST Design Environment, or prove solver completion, convergence, passivity or save/reopen
persistence. Keep these claims separate from successful file generation.

## Parameter-study history

For sequential EM points, `set_parameters` → `app.update()` (session-owned) →
`solve` is distinct from a native Parameter Sweep. Do not call full `Rebuild`
after the parameter update: CST documents that it deletes all results. For
acceptance check two geometry parameter combinations and all four complex S
leaves with positive 3D IDs and their actual parameter combinations, both before
and after native save/close/reopen. A successful SDK update alone is not proof
of persistence; retain independent per-case complex exports and logs.

For manual EM parameter changes followed by EM/HB reruns, require the bound native
postprocessor to regenerate the matching curves automatically and retain curves for
other parameter combinations. Verify HB storage, derived-result association and
Navigator comparison separately. One positive ID or a missing parameter legend does
not prove storage is off. Until native association is verified, automatically write
unique per-parameter Results snapshots with complete complex archives; never replace
one shared leaf across parameters. See [automatic refresh and parameter history](../../../docs/guides/hb_parametric_storage_and_length_results.md)
for setting gaps, fallback and two-combination/save-reopen acceptance. Do not modify
an active scan or report offline checks as end-to-end native acceptance.

Use `cst_solver.circuit.StudyResult(batch_path)` for immutable per-case snapshots, parameter filtering, complex curve reads and component comparisons. Preserve case status and source EM/circuit evidence; the source run 0 is metadata, not a stable historical handle. Native summaries are grouped under Results/Studies by batch/result/component/case. `verify_project()` checks saved native leaves against archived arrays without closing/reopening CST; report saved_readback_verified separately from native reopen acceptance. Keep the project result directory with the .cst until single-file packaging has been verified. See [parameter studies](../../../docs/guides/circuit_parameter_studies.md).
