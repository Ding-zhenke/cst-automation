# CST → ADS field-circuit handoff

- Export the linear EM network in Touchstone format with all device and control ports, reference impedances and port order. Record the CST project, positive Run ID, export settings, frequency coverage, and SHA-256. Keep any synthetic DC endpoint explicitly labeled and verify its provenance.
- Reconstruct nonlinear devices, grounds, port terminations, DC bias and control source in ADS from the actual CST schematic and model parameters. Check pin polarity and the netlist; matching an SNP alone does not establish circuit equivalence.
- Use an independent output directory, preserve the exact ADS netlist and native log, and read the native dataset. Compare the same frequencies, source amplitudes, harmonic truncation, interpolation/extrapolation and normalization; count coincident mixing products at the physical frequency coherently.
- Report carrier ratios separately from pumped incremental S-parameters. Compare both directions, reflections and actual junction voltages when relevant; preserve warnings and convergence limitations. A CST–ADS discrepancy does not by itself identify which solver or interface is wrong.
- This handoff does not authorize modifying CST source projects, restarting ongoing solvers, or changing circuit topology; follow the user's instructions and the applicable CST skills.
