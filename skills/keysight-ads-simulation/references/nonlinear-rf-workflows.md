# Nonlinear RF workflows

Use this reference for a mixer or oscillator, and for nonlinear amplifier or switch measurements such as compression, harmonics, intermodulation, or load pull. The rules below are grounded in the local ADS 2026 Update 1 installation at `D:\Program Files\Keysight\ADS2026_Update1`; route uncertain controller or component properties through [official-doc-index.md](official-doc-index.md).

## Common contract

Keep build, solver, and performance verdicts independent. The default `flow` proves a correctly represented nonlinear problem, successful solver/log classification, and finite expected dataset content. Only explicit `release` applies user-defined limits, corner or sweep coverage, robustness comparisons, and performance pass/fail.

Record tone order, powers, impedances, bias, harmonic and mixing orders, oversampling, oscillator-search settings, requested spectral products, phasor convention, and frequency/amplitude tolerances before simulation. Select the intended HB block and signal by identity; a dataset's existence or a converged but physically wrong setup is not acceptance.

## Mixer

### Build contract

For an ordinary two-tone large-signal mixer smoke test, configure LO and RF as the two harmonic-balance fundamentals. Put the LO, normally the largest and most nonlinear tone, in `Freq[1]`, and put RF in `Freq[2]`. **IF is an output**, not a third fundamental. Declare a separate IF or `SS_Freq` only for the documented small-signal mixer analysis that requires it.

- Ground the negative terminals of both one-tone sources and provide all required DC return paths.
- Name the output node, define source/load impedances, and verify the saved `instance.parameters` and emitted netlist.
- Use `MaxOrder >= 2` so sum/difference products are represented. Select LO/RF harmonic orders from the requested model, bandwidth, accuracy, and convergence needs; record the chosen values and compare order or oversampling settings when truncation affects the requested metric. Do not impose a fixed pair of harmonic orders as a universal default.
- With LO as fundamental 1 and RF as fundamental 2, RF-minus-LO is identified by `Mix[1] = -1` and `Mix[2] = 1`. If tone order reverses, derive the indices from the actual frequencies. Match both mix indices and frequency within a numerical tolerance.

### Default flow

Run one isolated HB case, classify the log, open the intended HB block, and require a finite nonzero IF complex value plus at least one expected source tone or other nonlinear combination. For the ordinary difference product, compute `f_IF = |f_RF - f_LO|` (equivalently, `IF = |RF - LO|`) from the requested tones and match it within an explicit numerical tolerance. As a non-normative arithmetic example only, tones at 1.0 GHz and 1.1 GHz differ by 100 MHz; those values are not a default test specification. This demonstrates the mixer flow but does not establish conversion gain, isolation, compression, match, noise, or hardware performance.

When `V` is a peak complex voltage across real load `R`, compute available power as `P = |V|^2 / (2R)` and then dBm. State the convention; do not silently treat a peak phasor as RMS.

### Release additions

- Apply explicit conversion-gain/loss, LO-RF-IF isolation, input/output match, compression, intermodulation, spur, and noise limits only where the model and analyses support them.
- Run every required RF-frequency, LO-power, input-power, bias, temperature, model, and impedance sweep. Compare truncation/order or oversampling settings when precision is material.
- Reopen and rerun into a separate output root, compare netlist hashes, product rows, metrics, and warning classes, and retain both runs.
- Label behavioral-model results as model-bounded and ideal ring isolation as an ideal symmetry upper bound rather than a hardware guarantee.

## Oscillator

### Build contract

Use ADS harmonic-balance oscillator analysis to solve the unknown oscillation frequency and steady-state spectrum. In ADS 2026 U1, the preferred node-identification method is **OscProbe**; it identifies a suitable node, or two nodes for a differential oscillator, in the active-device feedback path or resonant tank. Do not choose a DC-only bias node or output-buffer node.

An **OscPort** or differential `OscPort2` is the supported alternative when its insertion into the feedback loop is appropriate. Configure oscillator mode consistently with the chosen method. `Freq[1]` normally represents the unknown oscillator fundamental with fundamental index 1; provide a realistic initial frequency/search range and adequate harmonic order.

Verify device bias, feedback/tank connectivity, the selected oscillator node or OscPort location, output/load isolation from the resonator when appropriate, controller parameters, and emitted netlist before solving.

### Default flow

1. Run one isolated oscillator HB analysis and require solver completion without fatal or license errors.
2. Select the oscillator result block and verify a finite solved fundamental frequency, finite nonzero fundamental output, and the expected harmonic-axis structure.
3. Report frequency and spectrum from the parsed `.ds`. This proves the oscillator flow only; it does not prove startup margin, output-power specification, tuning range, pulling, phase noise, or hardware operation.

### Release additions

- Apply explicit oscillation-frequency/tuning-range, output-power, harmonic, current, efficiency, mode-selection, startup or loop-margin, load-pull/pushing, and corner limits supported by the model.
- Enable and validate **phase noise** only as an explicit release requirement. Record offset-frequency sweep, selected output node, carrier/harmonic settings, noise contributors, and units such as dBc/Hz; inspect the exact phase-noise variable and axis in the current dataset.
- Use adequate sideband/noise mixing settings and compare numerical settings when small-offset phase noise is sensitive to truncation or matrix stability.
- Reopen and rerun in a new directory, comparing solved frequency, requested spectral or phase-noise points, logs, and netlist hashes.

Local routes include `HB_Configuration_-_Oscillator.html`, `Harmonic_Balance_Simulation_for_Oscillator_Analyses.html`, `Oscillator_Phase_Noise_Analysis.html`, and `%HPEESOF_DIR%\examples\RF_Microwave\LearnOsc_wrk.7zads`.

## Convergence and evidence

Before changing tolerances, confirm topology, bias/DC paths, tone definitions, oscillator nodes, harmonic/mixing order, and oversampling. Use detailed solver status to separate nonconvergence from precision/truncation warnings. Too few harmonics can converge inaccurately; too many can create an ill-conditioned problem.

Retain the netlist, combined simulator log, dataset block/axis inventory, selected rows, formulas, CSV/JSON, and run paths. Mark an unexecuted release metric `not verified`; do not turn solver success into a performance pass.
