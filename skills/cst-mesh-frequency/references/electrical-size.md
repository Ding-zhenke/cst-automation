# 电尺寸、成本和代表频点

Estimate each overall dimension and relevant propagation length in wavelengths
over the band. Start with lambda0=c/f and material wavelength lambda0/n using
the applicable dispersive material or mode index. Record which index is known
or approximated; high-permittivity regions can be electrically much larger than
the free-space estimate. For strongly lossy/dispersive media consider complex
propagation constant and penetration depth instead of a lossless-index shortcut.

Combine electrical extents with thin films, contacts, gaps, ports, curvature and
anticipated global/local mesh density. Use prior cells/DOF and memory/timing if
available; otherwise label the cost estimate provisional. There is no universal
size threshold that makes a mesh adequate or automatic adaptation affordable.

- Electrically large or expensive geometry: usually keep the **Adapt. checkbox
  on the Automatic row off**, and select a few Single rows for adaptation.
  Two or three points covering band edges and a representative interior mode
  or resonance are an initial choice. Adjust for narrow resonances, dispersion,
  port cutoffs and field localization; do not certify a band from a fixed trio.
- Electrically small, affordable geometry: Automatic-row adaptation can be
  appropriate. Explain the electrical-size/cost reason and bound the pass budget.
- Preserve a justified accepted mesh when continuing comparable work. A new
  geometry or field-localizing material state can invalidate its suitability.

Explain the estimate, chosen adaptation frequencies/mode and expected cost
before settings are applied. A choice of a few points is conditional, not a ban
on automatic adaptation and not permission to weaken convergence targets.

For nonlinear downstream use, the highest retained mixing frequency is a data
coverage requirement, not automatically a mesh-adaptation frequency. Before
carrying standalone subcomponent settings into a larger assembly, reassess cost
using the assembly's extent, ports, local features and available memory. Record
adaptation points, pass/growth limits and prior memory/timing in the workflow
checkpoint. Reuse a previously accepted cost-controlled strategy for comparable
iterations; justify any reset to broader adaptation. Reaching a pass cap is not
convergence. Review native memory/disk-solver warnings before proposing a restart;
do not automatically stop a live solve or relax numerical acceptance.
