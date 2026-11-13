# CST → ADS field-circuit handoff

- Export the linear EM network in Touchstone format with all device and control ports, reference impedances and port order. Record the CST project, positive Run ID, export settings, frequency coverage, and SHA-256. Keep any synthetic DC endpoint explicitly labeled and verify its provenance.
- Reconstruct nonlinear devices, grounds, port terminations, DC bias and control source in ADS from the actual CST schematic and model parameters. Check pin polarity and the netlist; matching an SNP alone does not establish circuit equivalence.
- Use an independent output directory, preserve the exact ADS netlist and native log, and read the native dataset. Compare the same frequencies, source amplitudes, harmonic truncation, interpolation/extrapolation and normalization; count coincident mixing products at the physical frequency coherently.
- Report carrier ratios separately from pumped incremental S-parameters. Compare both directions, reflections and actual junction voltages when relevant; preserve warnings and convergence limitations. A CST–ADS discrepancy does not by itself identify which solver or interface is wrong.
- A native ADS SP analysis of nonlinear diodes linearizes around its DC operating
  point; zero external bias and pump identify the excitation, not a numerically
  observed internal DC voltage. If the operating point was not exported, report
  it as unavailable; do not manufacture one. Preserve actual port impedances.
- Extract actual diode terminal A−K voltage from the dataset with polarity,
  units, DC and pump/RF components, rather than substituting source settings.
  At coincident physical frequencies (for example an RF tone equal to a pump
  harmonic), the spectral value is their coherent sum and is not independently
  attributable to either contribution. Finite-power HB carrier ratios are not
  pumped incremental small-signal S parameters.
- Keep total process/solver stopwatch time and HB-analysis internal time as
  separate labeled quantities. Preserve truncation warnings and compare order
  when needed; a completed run and residual alone do not prove harmonic accuracy.
- A coverage or sweep checkpoint may predate separately submitted retry runs.
  Reconcile actual run receipts, identities, artifact hashes and completed axes;
  do not treat a stale coverage file as the current completion index, or overwrite
  original failed attempts when rebuilding a summary.
- This handoff does not authorize modifying CST source projects, restarting ongoing solvers, or changing circuit topology; follow the user's instructions and the applicable CST skills.
