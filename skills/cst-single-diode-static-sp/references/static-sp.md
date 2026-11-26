# Same-project single-diode static SP

## Junction geometry and terminals

Follow [CST modeling](../../cst-modeling/SKILL.md) for the parameter preview and geometry approval, and [diode loading](../../cst-diode-loading/SKILL.md) for the interface. Model the passive microstrip, substrate, ground and diode contact geometry.
For finite-width contacts, span the facing A/K contact edges with a discrete
face port. Size the edges to the actual contact footprint. Place the diode
only on the schematic in this representation. Preview the geometry, both
edges and the voltage direction before building. For board-edge feeds or a width-change comparison, follow the [finite-width contact checks](#microstrip-diode-replaced-by-an-em-port). Review actual A/K,
EM port number, mode, orientation, reference plane and reference impedance.
With two RF access ports and one junction port, the bare EM source is a
three-port network. Preserve any pad or package parasitics in their intended
representation exactly once.

## Self-MWS wiring and SP setup

Use one parameterized `.cst` for the 3D model and Design Studio schematic. During model setup, inspect the same project's automatic self-MWS schematic
block and map actual pins to all three EM ports. For a floating series
junction, enable **Show Port References** before wiring. The native
`Block.SetDifferentialPorts(True)` setter exposes the second terminal;
`Block.GetDifferentialPorts()` and the native pin list verify the setting.
Expose the references before adding nets. Where the loaded runtime provides
`app.circuit.expose_em_port_references`, use it and inspect the returned pins.
Wire A and K to the two intended terminals of the junction port. Terminate
the RF references according to their actual 3D return and wire the two RF
signal pins to measurement external ports. A grounded shunt junction can
use the default implicit schematic reference when the mapped K terminal is
the intended return. With exposed references the schematic has two pins
per physical EM port, and the EM S-matrix dimension is still three. Use
`app.circuit.configure_nonlinear_model` for the reviewed diode model and
`app.circuit.apply` for the connections with the native `list_pins` names.
Record the model settings or SPICE card digest.

Create one named S-Parameters task or reuse the selected existing task. Follow the [circuit skill](../../cst-circuit/SKILL.md) and check the loaded runtime and worker for the applicable setup and readback operations. Set a finite sampling band covered by the EM data, an explicit grid and numerical
reference impedance for each measurement port. Keep the static measurement
excitation enabled and check the specified static bias and pump-off condition,
including residual source impedances and the DC return. For a zero-bias case verify zero external DC. For a biased on-state case verify the actual diode operating point. Check the actual
output grid after execution because the supported native getters do not read
the sample count. Save and inspect the 3D model and schematic together.

## Case inputs and native execution

For an authorized geometry-change run, the workflow explicitly writes and reads back the
parameters, regenerates the geometry, solves EM and verifies the current
complete native EM matrix and stored parameters. Run the existing SP leaf
using the owned session and its applicable guarded interface after the EM
receipts match the case. Recheck the self-MWS link and source identity. For
diode-only changes, set and read back the resolved property value and its unit
for each case before running SP. If the loaded runtime supports an expression
binding, verify the saved property expression and the value stored with the
next SP result. Reuse matching EM data when its
input geometry and the native cache identity are unchanged. A parameter
edit or rebuild alone does not execute SP or publish a file.

Select the execution interface by its topology and source conditions. The
`native-static-sp-v3` zero-bias route requires the specified 50 Ω control chain.
Before any dependent solve, check the loaded worker and the single-diode case against
the [integration contract](../../../docs/guides/diode_workflow_integration.md) and
[public API](../../../docs/PUBLIC_API.md). A standalone embedded Touchstone circuit
is useful for an independent comparison of the loaded network. The same-project
validation requires the actual self-MWS block to supply the SP task.

## Export the loaded two-port

For a saved case, select its existing native SP result and export the four task-scoped
complex S-curves from the selected native schematic run as `static.s2p`.
Use `CircuitResult(project_path)` to locate the actual schematic tree paths and
Run ID. Assemble the matrix as `S[k, i, j]` (frequency, response port, excitation
port) for `cst_automation.touchstone.write_touchstone`. Parse the output and
compare S11, S21, S12 and S22 to the corresponding complex source curves.
Validate all values and their common frequency axis. Record the actual RF
port order and use the common real reference impedance of the SP result;
the Touchstone v1 writer does not renormalize. The optional `em.s3p` archive
comes from the separate 3D result and retains the junction interface for later
circuit loading. Archive each requested output with its respective run identity,
parameters and hashes. Export a new case to its own directory and publish
it automatically only after the current case passes the result checks.

## Parameter-change verification

When validating a parameter-triggered export, exercise the chain with two distinct values of the requested parameter, using
the original schematic and task. For each case, establish the actual 3D and
schematic result identities, confirm all four complex SP curves came from the
intended task, and compare the parsed `.s2p` with those curves. Choose a parameter
change expected to affect the response and check the changed response against
the prior case. Confirm the first archive survives the second update; successful
export alone does not prove CST preserves earlier native results after a rebuild.
Describe automation by its verified trigger, such as the parameter-run command
or an actually bound and exercised native post-processing task.

## Microstrip diode replaced by an EM port

For finite-width terminals, preview the two contact edges of each face port at
each requested width. For board-edge excitation, place the RF feed planes at
the substrate ends, with equal-width contacts on strip and ground. Mark the
substrate ends and outer simulation boundaries separately. At the floating
junction, pick the facing pad edges and identify the physical anode and cathode.
Use the [microstrip contact example](../../cst-modeling/references/model-operations.md#微带接触边)
for the pick order. After approval, check the realized face widths, polarity
and connectivity to the diode on the same project's schematic.

To validate a width-triggered static Touchstone export, vary only the line width
and hold the diode model and bias fixed. For each width, record the actual
three-port EM run, two-port schematic SP run, and the file produced by the
configured export task. Check both port order and reference impedance. Compare
all four complex S-parameters on their frequency grid with that SP run, retain
both files, and report the measured difference between widths. For CST-native
export, record the task sequence and its actual trigger.

## CST-native postprocessing trigger

Follow the [Design Studio Touchstone template procedure](../../cst-result-templates/references/touchstone-export.md#design-studio) using the owned session and its advertised template capability. Bind the actual static SP leaf to the Post task and verify its activation and SP → Post sequence after save/reopen. For a width-triggered workflow, also inspect the width-to-geometry binding and how the parameter run updates EM and invokes that sequence. Report the configured trigger. When execution is requested, identify the fresh native file and compare it to that case’s four complex curves. Record the complete parameter state independently of the native parameter sidecar, which may contain only changed parameters.
