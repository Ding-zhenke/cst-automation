# Configure S-Parameters → Touchstone Export

The examples use the installed VBA template in CST 2026.1 (20251022). Here `app` owns the idle, saved project.

## 3D project

With no `post_task`, the step is added to the project's
Result Templates list. This example requests 37 complex samples in RI format
at 50 Ω for export after a solver run.

```python
receipt = app.add_builtin_result_template(
    "S-Parameters", "Touchstone Export",
    settings={"NumberOfSamples": 37, "FormatG": "RI", "ReferenceImpedance": 50},
)
```

`FormatG` accepts MA, RI or DB. Use `LimitFreqRange=True` with `FMin` and
`FMax` to restrict the export band. For a second instance, supply a unique
`result_name`; reusing the name raises an error.

## Design Studio

For an existing SP task named `StaticSP` in the sequence
`SPAndExport`, create a sibling Post task and bind the template to the SP data.
Use task paths relative to the native Tasks root.

```python
receipt = app.add_builtin_result_template(
    "S-Parameters", "Touchstone Export",
    post_task=r"SPAndExport\ExportPost", create_post_task=True,
    settings={"TaskName": r"SPAndExport\StaticSP", "ReferenceImpedance": 50},
)
```

Omit `create_post_task=True` when appending to an existing Post task. DS
accepts `TaskName` and `ReferenceImpedance`. To export on each sequence
update, check the native order is **StaticSP → ExportPost**. Running the Post
task alone can export the source task's saved S-parameters.
