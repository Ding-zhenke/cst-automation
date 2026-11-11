# Environment and compatibility

## Validated baseline

The currently validated machine has ADS 2026 Update 1 at `D:\Program Files\Keysight\ADS2026_Update1`, Design Environment API 635, ADS-bundled CPython 3.13.2, and `keysight-edatoolbox` 1.2.5. Detect and report the live values on every run. Do not silently claim that a workflow validated on API 635 is compatible with another release.

## Mandatory preflight

Perform these checks before creating or changing ADS content:

1. Resolve the ADS root in this order: explicit user/CLI value, existing process `HPEESOF_DIR`, then a known local installation. Fail with a clear message if resolution is ambiguous.
2. Set process-scoped `HPEESOF_DIR` **before** importing `keysight.ads.de`, `keysight.ads.dataset`, `keysight.ads.dds`, or `keysight.ads.ael`. Importing DE without it raises `RuntimeError: HPEESOF_DIR must be set.`
   In ADS 2026 Update 1 external automation, import `keysight.ads.dds` before `keysight.ads.dataset` when both are needed in one process; the reverse order raises an explicit runtime error.
3. Prefer `%HPEESOF_DIR%\tools\python\python.exe`. Alternatively, use a virtual environment created from that interpreter with `--system-site-packages`.
4. Record:
   - resolved ADS root and interpreter;
   - Python major/minor version;
   - `keysight.ads.de.version()` and `keysight.ads.de.product_version()`;
   - EDA Toolbox and Dataset package versions when available;
   - whether the DE, Dataset, DDS, and EDA Toolbox imports required by the task succeed;
   - simulator executable paths and license-related failures.
5. Keep the preflight process short-lived. Importing DE and DDS checks out their corresponding licenses and holds them until the Python process exits.

Do not use `ads.exe -h` as an unattended health probe on this installation; it opens a modal ADS Launcher usage dialog. Use the version APIs and filesystem checks instead.

## Python and wheel compatibility

- A virtual environment's Python major and minor versions must match ADS. For this baseline, the complete DE/DDS/AEL stack is built for CPython 3.13.
- Create a new virtual environment for each ADS release. An environment created for another release may not work even if imports appear similar.
- Install the complete requirements from `%HPEESOF_DIR%\tools\python\wheelhouse\venv_requirements.txt` with the same wheelhouse as the source. Do not mix ADS wheels from different releases or install only a Dataset wheel and infer that DE/DDS automation is available.
- ADS 2026 uses PySide6 rather than PySide2. Update custom Qt imports and behavior accordingly.
- Treat `keysight.ads.dds` as officially supported for ADS 2026 Update 1. Earlier 2026 documentation described portions as beta; apply a version guard before using it on older installations.
- Do not make `dds.experimental` or another experimental API a required path.
- Use `DDSFile.print_all_pages` or `print_pages_by_name`, selecting PDF or PNG by output extension. The older `*_to_pdf` methods are deprecated and scheduled for removal in ADS 2027.

## Application and automation modes

- External automation can call `keysight.ads.de` when the environment and Python packages are configured.
- The embedded console is available in ADS through **Tools > Python Console**. Application mode can interact with open UI objects; automation mode cannot assume a GUI exists.
- Guard application-only behavior with `de.is_pde_app()` and `de.running_automation()`.
- AEL functions may be unavailable in automation mode. Before using the bridge, also test `ael.call.is_function_defined(...)`.
- Keep the automated build, simulation, Dataset, and DDS file generation headless. Launch or use the GUI only for final visual inspection of the saved artifacts.
- In `keysight-edatoolbox` 1.2.5, `CircuitSimulator.run_netlist()` delegates to `subprocess.check_call` and returns `None` on success; a nonzero process code raises `ExecutionError`. Record this explicitly as `return_code=0` with source `subprocess.check_call_success_no_exception`, preserve the full simulator log, and never interpret an arbitrary `None` from another API or version as success without verifying its implementation.

## License environment

- The ADS product license search variable is `ADS_LICENSE_FILE`.
- Prefer an explicit `port@license-server-machine` value on Windows; omission of the server TCP/IP port can cause checkout failures.
- Check a server with `lmutil lmstat -c <port>@<server>` when the tool is available and the user has supplied the server.
- Set `HPEESOF_DEBUG_MODE` before starting ADS to enable client license debugging; direct its output with `AGLM_DEBUG_LOG` when a persistent log is needed.
- Avoid `FLEXLM_DIAGNOSTICS=3` on Windows for this ADS generation because the official release notes identify a possible crash during license checkout. Use level 1 or 2 if FLEXlm diagnostics are required.
- Do not change license-server configuration, stop daemons, or borrow licenses without explicit authorization.

## Workspace safety

- `de.create_workspace(path)` requires a path that does not already exist.
- `de.open_workspace(path, force=True)` can close the current workspace and discard unsaved changes. Do not use `force=True` without explicit authorization and a confirmed save state.
- Opening a workspace changes the process current directory. Preserve the original directory and restore it when the automation finishes.
- Generate unique workspace and run-output paths by default. Inspect before writing, and refuse an existing path rather than cleaning or replacing it.
