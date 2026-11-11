# Troubleshooting and evidence classification

## Diagnose in layers

Work from the earliest failing layer and preserve the original text:

1. ADS root, Python interpreter, and environment variables.
2. Python package imports and API/product version compatibility.
3. License server reachability and feature checkout.
4. Workspace/library/model resolution.
5. Schematic topology and generated netlist.
6. Simulator return code, fatal errors, and convergence.
7. Dataset blocks, variables, and numerical acceptance.
8. DDS generation, dataset binding, structural reopen, and optional visible rendering when explicitly required.

Do not collapse every line containing `warning` or `error` into the same status. Classify evidence as at least:

- fatal simulator/design error;
- license error;
- convergence failure;
- numerical precision/truncation warning;
- optional library-definition warning;
- informational output.

Success requires no fatal error and no license rejection, plus analysis-specific numerical evidence. A zero process return code or a newly timestamped `.ds` file alone is insufficient.

## Preserve useful artifacts

For each run retain:

- preflight/version record;
- workspace and design identity;
- exact generated netlist;
- simulator command or `CircuitSimulator` parameters;
- `output_file` containing combined simulator stdout/stderr;
- return code;
- dataset path, block/variable inventory, and extracted metric;
- DDS path and optional PNG/PDF export;
- reopen/rerun comparison.

Generate netlists to named files and use a distinct output directory for every attempt. This makes stale datasets and changed inputs visible.

## SystemVue `vtb.defs` warning

A message such as an inability to include or locate SystemVue `vtb.defs` is not automatically a license failure. Classify it as an optional library-definition warning only when all of the following are true:

- the design does not use SystemVue/VTB content;
- the ADS circuit netlist and required model libraries resolve;
- the simulator completes without a fatal or license-checkout error;
- the expected dataset block and numerical result pass;
- reopen/rerun acceptance also passes when required.

If the design uses SystemVue, the missing definition prevents required model resolution, or the message is accompanied by a fatal error, treat it as blocking. Never globally suppress unknown missing-library messages.

## License failures

Identify explicit checkout evidence such as `FlexNet Licensing error`, `License checkout failed`, a denied feature, or an unreachable server. Keep these separate from `vtb.defs`, model-library, and HB precision warnings.

Treat `Cannot connect to license server system`, FlexNet/FLEXlm `-15` or `-96`, and failed/unable checkout messages as license failures. Treat `Error detected by hpeesofsim during netlist parsing`, `netlist flattening`, or `circuit set up`, and lines beginning with `ERROR:` as fatal simulator errors. An empty required simulator log is also blocking evidence, not a successful quiet run.

For a license failure:

1. Record `ADS_LICENSE_FILE` without exposing sensitive credentials or unrelated environment data.
2. Prefer an explicit `port@server` reference on Windows.
3. If authorized and available, run `lmutil lmstat -c <port>@<server>` to distinguish server/daemon reachability from feature exhaustion.
4. Use `HPEESOF_DEBUG_MODE` and `AGLM_DEBUG_LOG` for client debug output when needed.
5. Avoid `FLEXLM_DIAGNOSTICS=3` on Windows; use level 1 or 2 because level 3 is associated with a documented checkout crash.

Do not retry indefinitely, alter server configuration, or reinterpret a denied checkout as success.

## Simulator and convergence failures

- Inspect the retained netlist and output log before changing solver settings.
- Confirm component and model resolution, pin connectivity, grounds, DC paths, source/controller consistency, and requested output labels.
- For HB, verify all source tones are declared, LO is normally first, `MaxOrder >= 2` for mixing, harmonic orders are adequate, and an already generated harmonic/mixing frequency is not redundantly declared.
- Treat `More than one mixing term has landed on frequency...` as a setup warning requiring tone review.
- Treat a truncation warning as a precision concern, not automatically fatal; quantify its impact by increasing order/oversampling and comparing the target metric when needed.
- Use detailed solver status such as `StatusLevel=4` before changing tolerances or iteration limits.

The topology checker should normally remain enabled. A missing DC path to ground is a common cause of failure even when the drawing appears connected at RF.

## Classify topology warnings and model limits

- AC-coupled nodes can produce `no DC path to ground (topology corrected)`. Treat it as a topology warning rather than automatic failure only when the simulator completes, the correction is understood, and the numerical acceptance passes. Add an explicit high-value DC return when a physically explicit or warning-free topology is required.
- HB truncation warnings on diode mixers are precision warnings, not proof of convergence failure. Report them, increase harmonic order or oversampling, and compare the IF metric before claiming robustness.
- A behavioral mixer constrained by datasheet typical values can support integration and matching studies, but it is not a replacement for the vendor nonlinear model or hardware measurement. Label conversion gain, compression, noise, and leakage claims accordingly.
- An ideal transformer plus perfectly symmetric diode ring may report hundreds of decibels of isolation. Call this an `ideal symmetry upper bound`, not a physical prediction; include component imbalance, parasitics, loss, and layout coupling before making hardware-level claims.
- Do not claim S11 optimization when the model lacks a trustworthy nonlinear input impedance or port definition. Mark matching as unverified and defer it to a vendor model, impedance measurement, or VNA-guided tuning pads.

## Startup and GUI diagnostics

- Do not use `ads.exe -h` for unattended detection because it opens a modal launcher dialog on this installation.
- The installed `ads_verbose.bat` starts ADS in verbose/debug mode and writes `ads_daemon.log` at the root of the system disk. Use it only when ordinary preflight and logs do not explain startup behavior.
- Do not drive routine schematic construction by screen coordinates. If an operation is only supported in application mode, guard it and state why the GUI/AEL fallback is necessary.
- DDS automation can save and structurally reopen a file without opening a window. Use that path for default headless acceptance. A visible Data Display window is required only for an explicit visual-rendering claim; lack of a GUI is not a failure when UI appearance was outside scope.

### Full-application AEL lifecycle on Windows

Use `ads.exe -m <startup.ael>` only when an application-only AEL vocabulary is required. `subprocess.STARTUPINFO` and `CREATE_NO_WINDOW` suppress a console window; they do not reliably suppress the ADS Qt main window.

Before launch, snapshot the pre-existing handles. After launch, track the root process ID and any verified descendant process IDs. Hide only a new, automation-owned window whose title starts with `Advanced Design System`. Close only a new, automation-owned startup modal from an exact allowlist. On this installation the observed titles are `Get Started` and `Swap Component`; the latter can contain the message that another modal must be closed before ADS exits. Never close an unknown error dialog, a pre-existing window, or a window owned by another process. Retain the window-event records.

Do not rely on parent-process environment inheritance for an AEL status path. Render absolute workspace, rule, job, and status paths into a run-specific AEL driver before launch. If AEL `getenv()` returns `NULL`, `fopen()` reports a null first argument even when the parent shell contains the variable.

An ADS GUI process can exit cleanly with empty stdout/stderr. Empty application logs are acceptable only when the application return code is zero, the run did not time out, the non-empty status file contains all required fields, and the DVE job/report evidence independently passes. A timeout remains a failed application lifecycle even if partial status or job files exist; terminate only the launched automation process tree and preserve the partial evidence.

The ADS File Browser can show a project root while no workspace or design view is open. Do not use that screen as open-state evidence. Query `de.workspace_is_open()`, record the resolved workspace path and library/cell/view identity, then close/reopen and inspect the saved database when the validation level requires it.
