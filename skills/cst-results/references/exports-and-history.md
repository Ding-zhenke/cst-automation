# Export and retention of saved results

## Install Touchstone Export in the CST project

Use the [built-in result-template API](../../../docs/PUBLIC_API.md#add-an-installed-cst-result-template)
to append the installed S-Parameters → Touchstone Export step to an idle, saved
project. Omit post_task for MWS. For DS, pass the destination Post task and the
source S-Parameters TaskName, and schedule the Post task after the source.
Check the new native file and its header after execution. The registration
receipt covers saving and reopening. See the separate saved-sweep export below.

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
