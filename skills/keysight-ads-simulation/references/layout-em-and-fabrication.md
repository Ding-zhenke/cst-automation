# ADS layout, Momentum, and fabrication workflow

Use this reference for ADS 2026 Update 1 PCB/layout creation, substrates and padstacks, RFPro/Momentum simulation, or Gerber/Drill export. Circuit, layout database, EM solver, fabrication export, and performance are separate gates.

## Select `flow` or `release`

`flow` is the default and intentionally minimal. Execute only the physical stage requested by the user:

- layout: save/reopen the intended view and inspect the bound substrate/stack, essential nets, shapes, persisted pins/ports, port numbering, layers, pad/via objects, and unroutes from the database;
- Momentum/RFPro: verify the selected substrate and recorded plus/minus port map, run one requested frequency plan, require terminal solver evidence, and directly inspect the produced SIO, dataset, or Touchstone data;
- Gerber/Drill: perform one official export to a new directory, retain logs, inventory requested non-empty files, and report what was not deeply validated.

A `flow` result does not imply strict DRC, mesh convergence, drill-to-database parity, repeated-export hash equality, CAM round-trip validation, or an RF performance pass.

`release` is explicit and stage-scoped. It adds only the gates applicable to the physical stage currently requested; it does not launch Momentum, fabrication export, Drill validation, or a CAM import merely because another layout stage is in release mode. Classify candidate gates before execution:

- for a requested layout release: zero required unroutes and strict DRC/LVS or connectivity checks under the named ruleset;
- for a requested Momentum/RFPro release: separate coarse/fine or successive mesh runs, with the same physical metric meeting a stated mesh-convergence tolerance;
- for a requested fabrication release: parsed Drill tool/coordinate data, PTH/NPTH classification, hole counts, and board bounds agreeing with the design database;
- for a requested reproducible export release: close/reopen and repeat export into a new directory, followed by a SHA256 manifest and repeated-output hash comparison;
- for a requested round-trip release: Gerber/Drill CAM import and machine-readable geometry comparison.

Use `not applicable` when a gate does not belong to the requested stage or artifact. Use **not verified** when a gate is applicable but was not executed or lacks sufficient evidence. An executed applicable gate that misses its criterion is `failed`. Do not convert a flow pass into release acceptance.

## Evidence contract

Before editing, define the workspace, library/cell/view, substrate, layer-purpose pairs, padstacks, net and port names, requested stage, validation level, output directory, and any release thresholds in machine-readable configuration. Refuse to replace an existing workspace or run directory.

For every executed stage, write or retain status evidence containing source workspace/view, ADS version, invoked interface, output paths, warnings, validation errors, and a verdict. File existence alone is not a pass. A single-run hash may establish provenance in flow; only release compares it with a separately generated output.

## Create and inspect a physical layout

Use `keysight.ads.de`, `db_uu`, and the technology APIs. Do not hand-edit OpenAccess files.

1. Open or create the workspace and library before resolving layers or designs.
2. Create physical layers, material/substrate definitions, padstacks, and applicable rules before geometry.
3. Add copper polygons/paths with explicit nets. Create layout terminals with `add_dot_for_pin` plus `add_pin`; a generic conductive dot can exist in the database but does not provide a reliable edge-calibrated RFPro feed.
4. Create electrical through vias with `add_via_with_specified_layers(padstack, top_layer, bottom_layer, location, minimize_drills=False)`. A generic through-via helper can omit the explicit span and Momentum may omit the vertical conductor.
5. Save, close, reopen, and inspect the design database. Count shapes, SMD pads, PCBVia objects, nets, unroutes, and component sides from structured data rather than a screenshot.

Database inspection is the default flow gate. Zero-error DRC/LVS under a recorded ruleset is a release gate unless the user explicitly requests it as a standalone check.

### Synthesize controlled-impedance lines with LineCalc

Use ADS LineCalc for a nominal transmission-line starting point when the selected installed model matches the intended stack and ground structure. For CPWG, create a unique run directory, generate an AEL `.lcm` macro, save the native `.lcs` result, and parse that file into JSON with `scripts/run_linecalc.py`. Validate finite dimensions, the selected element ID, target impedance, and the model's documented applicability ranges. Treat only parameters listed by the native result under `PHYSICAL_FIXED` as fixed; LineCalc can recompute secondary values such as physical length while synthesizing another parameter. Compare every required fixed input with the `.lcs` value instead of trusting the macro request alone. Treat the result as a nominal analytical dimension; fabrication tolerance and final EM behavior remain separate checks.

On Windows, `linecalc.exe` can return zero before its `linecalcui.exe` child has written the `.lcs` file. Do not treat launcher return code zero as completion. Wait for a stable, non-empty native result, then clean up only the automation-owned child whose window title contains that run's unique absolute output path. Never enumerate and terminate every LineCalc or ADS process. Do not append `lcuiuser_file_exit()` to an unattended macro because it opens a confirmation dialog even after save.

After applying a synthesized width, rerun complete geometry, DRC, and EM checks. A valid straight-line width can still create a local clearance failure at a taper, pad, bend, via field, or connector transition.

### Add geometry DFM gates beyond DVE

Record the scope of every DVE rule. A clearance rule using `DifferentNetScope` does not detect a same-net inter-component pad overlap, so a zero-violation DVE report cannot by itself prove placement manufacturability. Add structured geometry checks for:

- same-net inter-component pad overlap, excluding intentional pad-to-trace contact within one footprint;
- minimum soldermask web and overlapping soldermask openings;
- silkscreen-to-pad clearance;
- copper transition polygons, tapers, paths, pads, and pours in the same clearance primitive set;
- local ground clearance and return continuity around a wide connector land and its taper;
- top-ground continuity, critical component courtyard/assembly spacing, and the post-route unconnected-net count.

Recompute these checks after any LineCalc width or gap change. A wider line can be electrically correct yet reduce the clearance beside a wide connector land or transition polygon below the fabrication rule. Save machine-readable offending object IDs, nets, bounds, and minimum distances so the result can be confirmed without a screenshot.

### Run DVE DRC in the full ADS application

In ADS 2026 Update 1, the `dve_create_drc_job` vocabulary may be unavailable from the external Python/AEL bridge even though it is available inside the full application. Launch a short-lived driver with `ads.exe -m <startup.ael>`, bind the exact layout view, and retain the DVE job directory and report. Hide only the new automation-owned ADS main window and dismiss only known startup dialogs; a “Get Started” window or “close this modal before exiting” message is not a layout error.

Instantiate workspace, rule, status, and job paths as absolute AEL literals before launch. A shell variable can exist in the parent process while AEL `getenv()` still returns `NULL`, causing `fopen()` to receive a null first argument. Do not use environment lookup as the status handshake for this path.

Place the deck as `<rule-root>/rules/<deck>.ael`. Pass the directory **one directory above** `rules` to `dve_job_set_rule_location_path`, set the rule folder to `rules`, and set the rule file to the basename. A terminal job with zero violations is insufficient: require application return code zero, successful DVE run status, report/job status `Complete`, empty job-error log, `totalRules > 0`, and `shapes > 0`. A `Complete` job with zero rules or zero shapes is an empty run and must fail release acceptance. Use `scripts/verify_dve_drc.py` for the pure evidence checks, AEL path instantiation, process-owned window classification, and ADS application-lifecycle validation. Read the full-application lifecycle section in [troubleshooting.md](troubleshooting.md) before automating `ads.exe -m`.

### Layer-purpose pairs

A physical layer is not automatically a usable layer-purpose pair. For a custom CAM layer such as `solder_mask_bottom`, create and save `solder_mask_bottom:drawing` through `keysight.ads.de.experimental.lpp.LppDb`. If the LPP is missing, Gerber can fall back to an unnamed numeric layer even though geometry appears on screen.

Use LPP APIs only after verifying the installed ADS version because they are under `experimental`. Reopen the library and confirm the named LPP persisted before export.

Do not assume a `PhysicalLayer` exposes `.layer_number` in every ADS 2026 U1 binding. Resolve a numeric layer through `LayerId.create_layer_id_from_library(library, layer_name, purpose).layer` after the library and LPP exist.

### PTH and NPTH representation

Use a drilled `PCBVia` for fabrication holes. In ADS 2026 Update 1, Drill export can ignore a **generic THROUGH PCBPad** even when its padstack contains a drill definition.

- Represent an electrical PTH with an explicitly spanned copper padstack.
- Represent an NPTH with a **No-Copper padstack** and an explicitly spanned `PCBVia`; classify it from the emitted drill tool diameter or a verified drill-layer map.
- Keep mechanical NPTH objects out of a separate EM-only view when RFPro would otherwise interpret them as copper barrels. Retain them in the fabrication layout.
- In flow, report design-database hole objects and exported files. In release, parse emitted coordinates/tools and compare PTH/NPTH counts and board bounds with the database; do not infer counts from filenames.

In ADS 2026 Update 1, **Design does not expose close()** in every Python binding. Use a tolerant release helper that calls `close()` only when present, then close the workspace through the supported API.

## Run RFPro/Momentum

Create or verify the RFPro view against the intended layout and substrate. Resolve every port from persisted layout pins, record plus/minus pin names and port order, and avoid holding a project modification context while starting the solver.

After adding ports or an analysis, drain the EM event queue until project validity remains stable; a single validity check can occur before an asynchronous connectivity update begins. Run the selected Momentum preset and wait for terminal `simulation.status`. Accept the solver gate only when it is `Completed`; process creation or a simulation directory is insufficient.

Preserve:

- analysis name, simulator, preset, frequency plan, mesh settings, ports, reference impedances, and feed types;
- solver details, elapsed time, simulation path, log, and preferred `work/proj.sio`;
- a converted ADS dataset or Touchstone file with explicit port-name comments and provenance.

For ADS 2026 Update 1, `empro.enparams._sio2adsds_discrete` converted `proj.sio` to `.ds`, but the leading underscore marks a version-fragile interface. Probe it before use and retain the source SIO. Use `keysight.pwdatatools` for SIO-to-Touchstone conversion and verify **Touchstone port order** against the recorded analysis port order.

In `flow`, search the log for `Calibration will not be used for port` and preserve it as a named port-calibration warning. Also record whether the log reports extracted vias when vertical conductors are expected. These observations qualify the flow result but do not by themselves block reporting a completed single-run solver path.

In `release`, an uncalibrated requested port is blocking: move the layout pin to a valid conductor/nonconductor edge and rerun. Missing via-extraction evidence is likewise blocking when the requested EM model contains expected vertical conductors. A release result cannot hide either condition inside a generic warning count.

One completed run with validated numerical output satisfies the default EM flow. For release mesh convergence, run distinct mesh settings into separate directories and compare identical physical metrics against an explicit tolerance. Record the exact settings and deltas; never call a single mesh run converged.

## Export Gerber and Drill

Use the Python-to-AEL bridge for official CAM functions when no equivalent supported Python API exists. The verified call order is:

1. Set `HPEESOF_DIR`, start ADS Python, and **open workspace**.
2. Open the layout design read-only and keep its handle valid.
3. Create/configure the Gerber exporter with `gbr_create_exporter`, then call `gbr_export_design`.
4. Create/configure the Drill exporter with `drl_create_exporter`, then call `drl_export_design`.
5. Release the design handle tolerantly and close the workspace.

Use an explicit JSON layer map, units, numeric format, scale, RS-274X format, `transfer_unmapped_layers=False`, and separate logs. The reusable `scripts/export_layout_fabrication.py` implements the verified millimetre raw-export sequence from JSON and refuses an existing output directory; other units remain unsupported until tested against the installed release.

For the default flow, require every requested CAM file to be non-empty, retain the official logs, and record an inventory. A SHA256 manifest may record provenance, but repeated equality is not claimed.

For release, parse Gerber geometry and Drill tools/coordinates, compare board bounds and PTH/NPTH counts with the design database, compute SHA256 hashes, reopen the source, and re-export into a new directory before comparing hashes. Read expected PTH and NPTH counts from the reopened source database for that run; never encode a project-specific constant in a reusable verifier. Perform the independent CAM round trip when it is a release requirement. If round-trip import and comparison were not executed, label that gate **not verified** even when source export succeeded.

### Import and verify the CAM round trip

Create a unique verification workspace outside the source workspace tree; ADS rejects a nested workspace. A sibling or separate verification root is safe. Stage CAM files under unique basenames, create an explicit import layer map, open the new workspace, then call `gbr_create_importer` and `gbr_import_design`. Close and reopen the imported design before collecting final evidence.

Require every requested Gerber destination layer to contain geometry, compare outline bounds and top/bottom copper area (or a stricter configured geometry metric) with the source, and generate review SVG/PNG from imported database objects rather than a screenshot.

ADS 2026 U1 can accept an Excellon input through `gbr_import_design` yet materialize **zero drill shapes**. Do not call that an official Drill-import pass. When the release contract permits a composite round trip, use an independent Excellon parser, verify tools/counts/coordinates against the source `PCBVia` objects, materialize the parsed holes on a dedicated verification layer, and disclose the official-import limitation. The composite drill-content gate may pass only when source-database count, parsed count, and materialized count agree, coordinates match, tool diameters are retained, and the limitation is explicit; otherwise mark Drill round trip `not verified` or `failed` according to the stated criterion. Use `scripts/verify_cam_roundtrip.py` for reusable parsing and evidence evaluation.

## Data-first review and verdicts

Read numerical and structural results from `.ds`, SIO/Touchstone, design-database objects, Gerber, and Excellon files. Generate CSV/JSON and script plots as needed. Use a GUI only for an explicitly requested visual criterion, and never take numerical acceptance values from screenshots when structured data exists.

Report circuit, layout database, Momentum, DRC/LVS, fabrication export, drill validation, CAM round trip, reproducibility, and RF performance separately as `passed`, `failed`, or `not verified`. An unavailable license or skipped release stage is not a pass.
