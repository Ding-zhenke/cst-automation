---
name: diode-isolator-design-workflow
description: Coordinate parameterized diode isolator design through CST EM, native zero-bias circuit S-parameters, ADS HB and evidence-based iteration.
---

# Diode isolator design workflow

Read this entire file and applicable referenced skills before dependent operations.
Use the current project configuration and original conversation session; never infer
device dimensions, model parameters, port mappings or targets from another project.

The sequence is parameters → CST EM → CST Design Studio S-parameters with diodes,
zero external DC and pump → ADS HB with separately specified bias and pump → joint
analysis → next candidate. The SP task's measurement excitation remains enabled.
Do not substitute 3D EM S-parameters, offline linear predictions or a pump-off
biased result for native zero-bias circuit SP.

For unchanged topology reuse the same CST project, path and window across candidates;
archive per-candidate inputs, matrices, raw outputs, logs and plots outside the
project without routinely copying the entire project. Verify actual native history
association and retention; a positive run ID alone is not persistence evidence.

Run noninteractive helpers, test processes and background solvers without opening
a console window. On Windows use `cst_automation.process.hidden_console_flags`
with existing process flags; keep pipes, logs, process groups and lifecycle rules.
An already detached worker must not combine `DETACHED_PROCESS` and
`CREATE_NO_WINDOW`. Interactive user tools and CST windows retain their own UI.

Use [sessions](../cst-sessions/SKILL.md), [circuit](../cst-circuit/SKILL.md),
[results](../cst-results/SKILL.md), and [ADS](../keysight-ads-simulation/SKILL.md)
for their actual stages and existing enforced gates. Bind results to the exact
geometry, materials, ports, model, source conditions and EM input. A changed ADS
bias or pump alone does not invalidate matching EM or zero-bias SP. Keep zero-bias
SP and HB source settings distinct. Never claim a configured task was executed.

The ordinary exploratory SP setup still rejects unsupported native sample-count
readback and does not adapt existing external ports and SP-task topology. The
separate fenced static-recovery route reads numerical constant impedances through
the project-bound native bridge, checks the actual result frequency axis after
the task, and can retain the reviewed existing topology. Its guarded run and read
interfaces are implemented and offline tested; actual native execution, sample
coverage and result identity must be established by that project's receipts.
The separate normal native-host v2 prepare/review/run/read route is offline tested;
it requires a compatible idle owned worker, actual preconfigured measurement ports
and reviewed topology, a verified 50 Ω control chain, GUI sample
observation and current EM evidence. Read the integration contract for exact
inputs and limitations. Native project acceptance and candidate reuse remain
pending; do not substitute the failure-recovery route or claim a completed loop.
Inspect each source's actual connection and impedance when adding measurement
ports. A zero-amplitude source may still load the same net, and a second port
impedance may create an unintended parallel termination; do not remove sources
and leave nets floating. See the integration contract for the evidence boundary.

For resumption inspect original CST job and session first; unknown or active jobs
must not be resubmitted. `cst_automation.workflow_resume.missing_cases` is only an
offline candidate list: verify actual artifact bytes, case identity, solver status
and validity before reusing or submitting any ADS point. This helper is not a
runner, state store, qualification gate or evidence of complete numerical results.
Project adapters may use the separate `cst_automation.design_state.DesignState`
SQLite journal to reserve requests and retain immutable attempts. Read the
[integration contract](../../docs/guides/diode_workflow_integration.md); its
caller assertions do not replace native receipts, archive checks or solver gates.

Report raw complex data, units and input identities separately from numerical
quality and performance conclusions. Preserve failures and independent mesh,
residual, sampling, DC-fit and HB-truncation evidence. Bounds on diagnosis and
resource use come from the project; do not silently relax acceptance thresholds.
