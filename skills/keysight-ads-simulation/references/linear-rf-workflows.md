# Linear RF workflows

Use this reference for an **Amplifier**, **Filter**, or **RF switch** whose primary acceptance data comes from DC and S-parameter analyses. If compression, harmonics, intermodulation, or another driven large-signal effect is required, also use [nonlinear-rf-workflows.md](nonlinear-rf-workflows.md).

The procedures and names below are grounded in the local ADS 2026 Update 1 installation at `D:\Program Files\Keysight\ADS2026_Update1`. Consult [official-doc-index.md](official-doc-index.md) before choosing an installed component definition or parameter name.

## Common contract

Keep three verdicts separate:

- **Build:** the saved schematic has the intended models, `instance.parameters`, bias network, ports, reference impedances, controller, and connectivity, and the generated netlist agrees with it.
- **Solver:** the current run has a successful process/log classification and the intended `.ds` block contains finite DC or S-parameter data on the requested axes.
- **Performance:** measured RF values meet explicit limits and tolerances. This is a `release` gate, not an implicit requirement of the default `flow`.

For the default `flow`, use a new output directory and run only the minimum analyses needed to prove the path: DC first when active bias or control state matters, then one S-parameter sweep, or the smallest representative state sweep for a switch. Report metrics but do not invent pass limits.

For explicit `release`, add the user's band edges, state matrix, bias and corner conditions, tolerances, performance limits, and applicable circuit-to-layout or circuit-to-Momentum comparisons. Reopen and rerun into a second directory, compare netlist hashes and metrics, and retain both results.

S-parameters are dimensionless complex ratios. Convert magnitude to decibels with `20*log10(abs(S[i,j]))`; do not use a voltage-to-power or `10*log10` conversion for an S-parameter. Preserve port numbering, `PortZ`/reference impedance, frequency, state, and other independent axes with every extracted row.

## Amplifier

### Default flow

1. Build the bias network, device or model include, input/output terminations, DC controller, and S-parameter controller. Give active nodes explicit DC return paths.
2. Run DC and verify the intended operating point: supply voltage, device currents, and requested node voltages must be finite and physically consistent with the setup.
3. Run the requested S-parameter band with the specified reference impedances. Select the exact SP block and extract `S[2,1]`, `S[1,1]`, and `S[2,2]` when present.
4. Report small-signal gain as `20*log10(abs(S[2,1]))`, plus input/output return loss or raw complex data as requested. Solver completion and finite gain prove only the flow, not gain, match, noise, stability, or power performance.

### Release additions

- Apply explicit gain, gain-flatness, input/output match, bandwidth, noise-figure, and stability limits over the stated frequency, bias, temperature, model, or statistical corners.
- If compression, PAE, ACLR, harmonics, or load/source pull is in scope, add the appropriate nonlinear analysis and explicit limits; a small-signal SP pass cannot satisfy those gates.
- When physical interconnect matters, compare schematic and Momentum/EM co-simulation data at identical ports, impedances, and sweep points. Treat differences as measured data, not visual judgment.

Local routes include `Amplifier_QuickStart_Guide.html`, the power-amplifier S-parameter example, and `%HPEESOF_DIR%\examples\RF_Microwave\RFIC\amplifier_wrk.7zads`.

## Filter

### Default flow

1. Build a two-port network with explicit terminations and an S-parameter sweep covering at least the requested passband or stopband point.
2. Validate finite `S[2,1]` transmission and `S[1,1]` reflection data on the expected frequency axis. Report insertion response, return response, and the observed crossing or extremum only when computed from the dataset.
3. For a distributed or layout-dependent Filter, generate or synchronize the layout, verify nets and port mapping, and run one requested Momentum analysis. Compare circuit and EM traces using the same frequency grid or a documented interpolation.

### Release additions

- Apply explicit passband ripple or insertion-loss, return-loss, cutoff/bandwidth, stopband rejection, group-delay, and out-of-band limits over every specified band.
- For a physical filter, require the selected substrate and conductor model, port map, a mesh-convergence comparison in separate run directories, and circuit-versus-Momentum deltas within stated tolerance.
- Keep ideal-lumped, PDK-model, layout-model, and Momentum results labeled separately; agreement at one point is not full-band correlation.

Local routes include `ex_lpf.py`, `Designing_a_Simple_Low_Pass_Filter.html`, and the installed Momentum microstrip-filter example.

## RF switch

Treat each bias/control condition as a distinct network state. A file or dataset from one state cannot establish the behavior of another.

### Default flow

1. Define a machine-readable state table containing control values, DC supplies, expected selected path, port numbering, and reference impedances.
2. Run DC for each required representative state and confirm finite control and device-bias values before the RF solve.
3. Run an S-parameter **state sweep** or isolated SP run per state. Preserve the actual state axis or state identifier in CSV/JSON.
4. In the selected ON path, report transmission such as `S[2,1]`; in an unselected path, report the corresponding isolation term. Also retain the relevant input/output reflection terms. Do not reuse one path's indices for another topology without checking the port map.

### Release additions

- Cover every required state and apply explicit insertion-loss, isolation, return-loss, amplitude/phase balance, and power-handling limits over the full frequency and bias ranges.
- Verify state-to-state mapping, control exclusivity, and any settling or transient requirements with the appropriate analysis rather than inferring them from a static SP dataset.
- For a physical RF switch, add layout/LVS or connectivity evidence and EM co-simulation where interconnect coupling matters. Compare identical state, port order, and reference impedance across circuit and Momentum results.

Local routes include `Designing_MMIC_SPDT_Switch.html` and `%HPEESOF_DIR%\examples\RF_Microwave\MMIC\MMIC_SPDT_wrk.7zads`.

## Data evidence

For every executed analysis, retain the generated netlist, simulator log, dataset block/axis inventory, selected complex rows, derived formulas, CSV/JSON, and the run directory. A plot is a presentation of parsed data, not an independent measurement. Mark skipped release checks `not verified` rather than converting them into a flow pass.
