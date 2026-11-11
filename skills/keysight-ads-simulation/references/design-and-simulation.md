# Design and simulation workflow

## Separate the three gates

ADS RF automation has three independent acceptance layers:

1. **Build gate:** the saved workspace/design and emitted netlist represent the requested circuit or physical hierarchy.
2. **Solver gate:** the selected simulator completed, its log has no fatal or license-checkout failure, and the intended current-run dataset contains valid data.
3. **Performance gate:** calculated measurements pass explicit limits and tolerances over the required sweeps, states, and corners.

The default `flow` requires the applicable build and solver gates and reports calculated values. It does not invent a performance specification. Explicit `release` adds the performance gate, reopen/rerun evidence, and the coverage named by the relevant RF-family or physical-design reference. A build pass cannot satisfy the solver gate, and solver success cannot satisfy performance.

## Build with the Design Environment API

Use `keysight.ads.de` and `keysight.ads.de.db_uu` for deterministic design creation. Follow the installed `ex_create_sim_and_plot.py`, `ex_lpf.py`, and analysis-specific official examples rather than inventing component identifiers or parameter names.

1. Resolve a new workspace path and verify it does not exist.
2. Call `de.create_workspace(...)`.
3. Create a new library with `de.create_new_library(...)` and add it to the workspace.
4. Create the required schematic or layout design unit with `db_uu`.
5. Add installed component definitions, wires, grounds, labels, ports, output names, sources, and the matching analysis controller.
6. Set parameters explicitly. Before assignment, **check that the parameter exists** on the instantiated definition. After assignment, enumerate or read `instance.parameters` and verify the stored value, expression, and unit; repeat the check after save/reopen and against the generated netlist. Do not accept a Python assignment merely because it raised no exception.
7. Validate definition identity, pin count, numbered-terminal connectivity, reference impedance, source/controller consistency, and required DC return paths.
8. Save the design, generate a netlist through the supported design API, and retain and inspect that exact netlist before simulation.

Do not hand-author workspace database files. A palette caption is not necessarily the programmatic component name. Resolve uncertain component and parameter names from the local ADS 2026 Update 1 documentation, examples, and API 635 definitions.

### ADS 2026 Update 1 API boundaries

- A `Design` object does not provide `design.transaction()`. Create `de.db.Transaction(design, "description")`, make the edits, and call `commit()` on that transaction.
- Do not infer pin locations from symbol coordinates. Resolve each numbered terminal and connect at `inst_term_numbered(n).inst_pins[0].snap_point`; this remains valid when the symbol rotates or its artwork changes.
- Parameter spelling, indexing, accepted expressions, and units are definition-specific. Verifying `instance.parameters` plus the netlist is the required evidence chain.
- Generate the netlist after saving, then inspect component models, values, node connectivity, port numbering, source fundamentals, sweep variables, and controller settings.

## Select the analysis from the measurement

| Analysis | Typical purpose | Minimum solver evidence |
| --- | --- | --- |
| DC | Bias point, control state, or swept bias | Intended DC block/axis, finite currents and voltages, understood topology warnings |
| AC | Small-signal transfer or impedance about a bias point | Expected frequency sweep and finite requested complex variables |
| S-parameter | Amplifier, filter, RF switch, or passive network characterization | Correct ports/reference impedances, SP block and sweep, requested complex `S[i,j]` rows |
| Transient | Switching, startup, waveform, envelope, or timing behavior | Expected time grid, finite waveform, requested timing/amplitude measurement |
| Harmonic balance | Mixer, driven nonlinear circuit, compression, or oscillator steady state | Correct fundamentals/search mode and order, convergence, intended spectral axes and products |

Record sources, terminations, controller parameters, output names, formulas, conventions, and requested tolerance before the run. Route amplifier/filter/RF switch measurements through [linear-rf-workflows.md](linear-rf-workflows.md), and route mixer/oscillator details through [nonlinear-rf-workflows.md](nonlinear-rf-workflows.md).

## Run and preserve solver evidence

Prefer `keysight.edatoolbox.ads.CircuitSimulator`:

1. Submit the generated netlist with `run_netlist(...)`.
2. Use a new dedicated run directory for every attempt.
3. Set `output_file` to retain combined simulator stdout/stderr.
4. Set `netlist_file` to retain the exact submitted netlist.
5. Supply `rel_data_dir`, absolute PDK directories, or other required model/data paths explicitly.
6. Record process-code evidence, classify the complete saved log, and then inspect the numerical dataset.

In EDA Toolbox 1.2.5, successful `run_netlist()` returns `None` because its internal `subprocess.check_call` returned normally; record exit code 0 only with that implementation-specific evidence. A nonzero code raises an exception. Do not generalize an arbitrary `None` from another API or release into success.

`output_dir` becomes the simulator working directory only when `working_dir` is omitted. If `working_dir` is supplied, datasets and simulator-created `<dataset>_data` directories are emitted there. Set it to the dedicated run directory, or omit it, when isolation matters; do not point it at the workspace root and assume output placement follows `output_dir`.

`CircuitSimulator.run(...)` and `run_netlist(...)` are blocking. Process completion alone is not a solver pass: require log classification and the intended current-run dataset block, axes, signals, and finite values.

Direct `hpeesofsim` is a fallback when EDA Toolbox cannot perform a documented requirement or when reproducing a low-level simulator issue. Its documented form is:

```text
hpeesofsim [ --MTS_enabled ] [-r output_rawfile_name] [netlist_inputfile_name]
```

Direct execution still requires the ADS simulator environment, libraries/configuration, and licenses. Preserve the command, environment summary, netlist, stdout/stderr, and output files. Text netlists are command-line inputs and cannot be simulated as text through the ADS GUI.

## Schematic, layout, and EM co-simulation

Treat schematic, synchronized layout, EM model/co-simulation view, and fabrication layout as distinct representations with separate gates.

1. Establish the schematic build and solver baseline first unless the task starts from an existing physical design.
2. Generate a layout from the schematic or synchronize the two through the supported ADS flow. Inspect the design-differences result, component mapping, hierarchy, nets, pins, port numbers, and parameterized layout values; visible similarity is not synchronization evidence.
3. Define the substrate, conductor stack, physical ports, and EM partition. Keep port order and reference impedances traceable from circuit terminals to Momentum/RFPro ports.
4. Generate or select the EM model or EM co-simulation view through a documented hierarchy policy. Verify that only the intended physical subnetwork is replaced and that active/lumped devices remain in the intended circuit domain.
5. Run the circuit and EM/co-simulation cases into separate output roots. Compare the same complex quantities on the same port map, reference impedance, state, and frequency grid using parsed `.ds`, SIO, or Touchstone data.

The default `flow` needs only the requested schematic-to-layout or single EM/co-simulation path and direct result inspection. Explicit `release` adds circuit-versus-EM performance limits, physical release gates, and reproducibility. Read [layout-em-and-fabrication.md](layout-em-and-fabrication.md) before manipulating layers, padstacks, vias, Momentum/RFPro, Gerber, or Drill data.

## Convergence triage

When a solver is inaccurate or fails:

1. Confirm model/library resolution, topology, grounds, DC paths, sources or oscillator search settings, controller consistency, harmonic/mixing order, and requested outputs.
2. Increase diagnostic detail, such as `StatusLevel=4` for HB, and inspect residual or iteration evidence.
3. Distinguish nonconvergence from truncation/precision and topology warnings.
4. Adjust tolerances, solver selection, iteration limits, oversampling, or harmonic order only after the represented problem is sound.

Too few harmonics can converge with inaccurate truncation. Too many can create an ill-conditioned Jacobian and slow or prevent convergence. A solver setting that produces a dataset is not automatically a physically valid model.

## Release reopen and reproducibility

Reopen/rerun is a `release` gate by default, or a separate explicit user request:

1. Save all design objects and record their paths.
2. Close the workspace through the supported DE API.
3. Reopen without `force=True`.
4. Re-read instance definitions and `instance.parameters`, regenerate the netlist, and rerun into a new output directory.
5. Compare signal/block identities, axes, requested metrics, warning classes, and simulator status using stated tolerances.
6. Compare the regenerated netlist hash with the baseline. A different hash requires a readable diff and explanation before metric comparison.

Never overwrite the baseline dataset or logs. A successful reopen without a fresh numerical rerun does not establish reproducibility.
