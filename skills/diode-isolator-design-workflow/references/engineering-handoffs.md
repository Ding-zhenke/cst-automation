# Diode workflow handoffs

## Microstrip diode replaced by an EM port

For finite-width terminals, preview the two contact edges of each face port at
both requested widths. For board-edge excitation, place the RF feed planes at
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

## Shared SNP input for ADS circuits and scans

When multiple ADS circuits or scans use the same CST-exported Touchstone network,
reference one canonical SNP file instead of copying a duplicate into each circuit
or scan workspace. Set its path once in the authoritative schematic/source
configuration and in any build or generation scripts; generated netlists must
inherit that setting (for example, their `File=` reference). Editing only an
already-generated netlist is not sufficient because regeneration can restore
per-workspace copies.

Prefer a project-relative reference resolved from a single shared project location
so the project remains movable. Before running a circuit or scan, verify that the
resolved path exists, is readable, and identifies the intended Touchstone file;
verify the schematic/source configuration, generated script output, and generated
netlist all resolve to that same canonical file. If the project is moved, repeat
the path-resolution check before reuse. Keep existing duplicate files in place
during migration; do not delete them as part of changing references. Archive or
record the canonical file's identity (including a content hash when practical) with
results so reused data can be traced to the exact network.

## Static SP routes

The ordinary exploratory SP setup still rejects unsupported native sample-count
readback and does not adapt existing external ports and SP-task topology. The
separate fenced static-recovery route reads numerical constant impedances through
the project-bound native bridge, checks the actual result frequency axis after
the task, and can retain the reviewed existing topology. Its guarded run and read
interfaces are implemented and offline tested; actual native execution, sample
coverage and result identity must be established by that project's receipts.
The separate normal native-host v3 prepare/review/run/read route is offline tested;
it requires a compatible idle owned worker, actual preconfigured measurement ports
and reviewed topology, a verified 50 Ω control chain, GUI sample
observation and current EM evidence. Read the integration contract for exact
inputs and limitations. Native project acceptance and candidate reuse remain
pending; do not substitute the failure-recovery route or claim a completed loop.
Inspect each source's actual connection and impedance when adding measurement
ports. A zero-amplitude source may still load the same net, and a second port
impedance may create an unintended parallel termination; do not remove sources
and leave nets floating. See the integration contract for the evidence boundary.
