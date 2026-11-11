# Dataset and Data Display

## Use data-first acceptance

Treat the ADS `.ds` dataset as the source of numerical truth. The normal headless pipeline is:

```text
ADS simulation -> native .ds read -> numerical checks -> CSV/JSON -> script plots -> hash and rerun comparison
```

Do not launch ADS merely to read values from a graph. Never estimate a marker, trace, axis crossing, gain, or tone level from a screenshot when the underlying dataset is available. A screenshot may document UI appearance, but it is not numerical evidence.

## Read and validate ADS datasets

Use the native `keysight.ads.dataset` API for ADS `.ds` files. Open through `dataset.open(...)` or a documented context manager rather than constructing Dataset objects directly.

An ADS dataset contains named `VariableBlock` objects with ordered independent and dependent variables. Convert a block with `VariableBlock.to_dataframe()` when pandas operations are useful. Dots in a block name such as `Optim1.SP1.SP` do not establish an actual nested hierarchy; enumerate the dataset and select the exact block.

For every simulation:

1. Confirm the expected dataset path and successful open.
2. Enumerate block names, variables, independent axes, units when available, row counts, and value types.
3. Select the intended analysis block and signal by exact identity, not merely the first block.
4. Check finite data and the expected sweep/time/frequency points.
5. Evaluate the requested metric with an explicit tolerance and impedance/phasor convention.
6. Cross-check the simulator return code and log classification.

Never accept a run solely because a `.ds` file exists. ADS may leave a dataset after a partial, failed, stale, or physically misconfigured run. Require the intended block, variable, current-run provenance, valid values, solver completion, and no fatal or license-checkout error.

For a two-tone HB mixer:

- The usual HB result block is named like `HB1.HB`; select it explicitly rather than assuming the first block.
- ADS 2026 Update 1 dataframe axes may appear as `Mix[1]` and `Mix[2]`. Column labels are case-sensitive, so discovery code should accept both `Mix[...]` and `mix[...]` forms and retain the actual label.
- With LO as fundamental 1 and RF as fundamental 2, the RF-minus-LO result has `Mix[1] = -1` and `Mix[2] = 1`. Verify both mix indices as well as frequency; a frequency match alone can be ambiguous.
- Locate the target frequency using a numerical tolerance rather than exact floating-point equality. Normalize independent variables from the index if `to_dataframe()` did not place them in columns.
- Verify the selected complex value is finite and nonzero and retain nearby spectral rows as evidence.
- If `V` is a peak complex voltage across a real `R`-ohm load, use `P = |V|^2 / (2R)` and `dBm = 10 log10(P / 1 mW)`. Do not use `|V|^2/R` unless the value is explicitly RMS.

## Export calculations and plots

Derive all review artifacts from the same parsed dataframe:

1. Write selected spectral rows and sweep tables to CSV.
2. Write metrics, units, formulas, reference impedance, tolerances, source dataset path/hash, netlist hash, and pass/fail fields to JSON.
3. Use a noninteractive backend such as Matplotlib `Agg` to generate PNG/SVG/PDF plots without opening ADS.
4. For mixer work, plot the RF-frequency sweep and LO-power sweep when those sweeps are part of acceptance. Annotate the expected IF relationship and acceptance threshold from the computed data.
5. Re-read the emitted CSV/JSON and recompute at least the key metric before reporting completion.

The plot is a presentation of the data, not a second measurement. Keep script-generated figures separate from DDS-rendering evidence.

## Create a Data Display file

Use the supported `keysight.ads.dds` API to create or modify `.dds` content:

1. Associate the display with the intended `.ds` dataset.
2. Create a page with a descriptive name.
3. Add the analysis-appropriate plot and one or more traces.
4. Add equations, text, labels, or a marker for the requested measurement, such as the requested mixer IF product, amplifier gain, filter response, switch state metric, or oscillator result.
5. Save the `.dds` file to a new or explicitly authorized path.
6. Export with `DDSFile.print_all_pages(...)` or `print_pages_by_name(...)`; choose PDF or PNG through the filename extension.

For ADS 2026 Update 1 automation, the `path` passed to `new_dds_file(dataset, path)` is an ADS workspace-style root and its default dataset directory resolves to `<path>/data`. When saving a new in-memory file, pass both `name` and the destination directory to `DDSFile.save(name=..., path=...)`; passing only `path` raises `No filename specified to save object`. If the DDS is saved outside its source workspace, ensure the destination has the expected `data` directory or use an absolute dataset reference.

Avoid deprecated `print_all_pages_to_pdf` and `print_pages_by_name_to_pdf` in new automation. Do not use `dds.experimental` for a required workflow when the stable API provides the operation.

When making a portable display bundle, copy the source `.ds` into the display workspace `data` directory and verify its hash. Reopen the saved DDS with `open_dds_file(...)`, inspect the dataset binding, page names, trace expressions such as `dBm(IF_OUT)`, and marker names such as `m_if`, then compare the marker target with the independently parsed dataset.

DDS objects are owned by the open DDS document. After closing and reopening a file, references to the earlier page, plot, trace, or marker are stale and may raise `Attempting to access a deleted object`. Cache plain strings and identifiers before closing, then reacquire all objects from the reopened document.

## Understand DDS operating modes

- **Application mode:** Run from the Data Display Python Console. Changes to open DDS objects can update displayed windows.
- **Automation mode:** Run outside ADS/Data Display. The API can create, edit, and save `.dds` files, but no interactive window should be assumed.

Importing `keysight.ads.dds` checks out and holds a Data Display license until the process exits. Keep the generator short-lived and record import or license failures.

Some DDS PNG exports use transparent backgrounds. Image viewers that composite transparent backgrounds as black can make the area outside the page appear black; this is a rendering artifact and says nothing about the numerical data. Prefer the script-generated plot for numerical review, or export to PDF/use an explicit background when appearance matters.

Saving a valid `.dds` file is not proof that its UI rendering is attractive, but UI rendering is not a default numerical acceptance gate. Use a visible Data Display window only when the user explicitly requests GUI/render verification or when page layout, fonts, clipping, colors, or interactive marker appearance is itself the requirement. Otherwise, programmatic reopen plus structural inspection and agreement with the `.ds` result completes the DDS gate, and the GUI check is not applicable.

## Reopen and compare

After closing and reopening the workspace and display:

- ensure the `.dds` file still resolves the intended dataset or the deliberately selected rerun dataset;
- ensure pages, traces, equations, and markers reload;
- confirm the target data point agrees with the separately analyzed Dataset value within tolerance;
- keep the baseline and rerun datasets separate so stale-data binding is detectable;
- regenerate the netlist, compare its hash with the baseline, and record any intentional difference;
- compare key metrics and warning classes through scripts, not screenshots.
