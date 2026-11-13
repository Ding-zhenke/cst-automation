# Diode workflow integration: current offline contract

This initial contract is project-owned bookkeeping, not an execution service or
an extra CST qualification gate. Keep the SQLite file in the project audit root.
Do not place it in the `.cst` companion or edit an active engineering session.

```python
from cst_automation.design_state import DesignState

journal = DesignState(absolute_state_database_path)
journal.register_project(project_id, absolute_cst_path, topology_digest)
identities = journal.begin_attempt(project_id, candidate_id, attempt_id, inputs)
reservation = journal.reserve(attempt_id, 'em', request_id)
if reservation['new']:
    pass  # the project adapter must use the existing protected session submit
# Query the original request on every recovery; never infer stopped from timeout.
journal.finish(attempt_id, 'em', request_id, 'failed', {'original_terminal_receipt': '...'} )
view = journal.snapshot(attempt_id)
```

`inputs` contains exactly five JSON objects: geometry, em, static_sp, ads_hb and
analysis. Put the full relevant source identities, parameters, model and units in
each object; a digest of incomplete inputs cannot certify equivalence. EM identity
uses geometry+em, static SP adds static_sp, ADS HB adds ads_hb to EM, and analysis
includes all. A changed pump only changes ADS HB and analysis identities; a
geometry change changes all four. Reuse remains a project-adapter decision requiring
actual artifact hashes and existing native qualification evidence.

Reservations are committed before returning, serialized across processes, and
idempotent for the same attempt/stage/request. A reserved row can represent an
unknown submission outcome after interruption: reconcile with the original
session, never treat reservation as proof that a native job started or finished.
An elapsed wait or timeout with unknown native status must remain reserved;
it is not a terminal failed receipt.
The adapter must persist request/job mapping, confirm terminal native receipts,
and verify artifact bytes. `complete` is a caller assertion, not library certification.
An attempt cannot rewrite its inputs or a terminal receipt; retries use new attempts.
This initial API does not enforce stage ordering, copy archives, perform operations,
resume ADS processes, verify artifacts or synchronize CST results. The project owns
these operations and should expose missing functionality as pending.

## Native zero-bias SP gap

### Native-host v3 operations (offline validation; native acceptance pending)

The following four operations supersede the earlier unpublished-host note below.
Use `submit_cst_session_operation` / `SessionManager.submit` on the same owned
saved project and an idle worker advertising `native-static-sp-v3` and
`static-sp-guarded-run-v1`. They never launch or upgrade a worker. Existing
`native-static-sp-v1` or `native-static-sp-v2` does not imply v3 support.

Prepare the actual host, diode blocks, control network, exactly two connected
measurement external ports first. The target SP task may be absent or an existing S-parameter **leaf**. Reuse
`circuit/build/configure`, `configure_nonlinear_model`, and the existing native
task/port setup where supported. If these exact objects are missing and cannot
be created by the current session interface, the engineering owner may use the
authorized GUI to create/connect those objects; do not remove the automatic host, change diode wiring, or launch it.
Inspect the complete circuit, actual host pins, units and task after setup.

The GUI-observed sample table for this one linear SP task is a UTF-8 JSON file
with exactly `source`=`gui_observation`, `task_name`, `frequency_unit`, `fmin`,
`fmax`, integer `samples`, timezone-bearing ISO `observed_at`, and `review_note`.
It is a human observation, not an SDK getter; the session reads it by absolute
path and SHA-256 and refuses stale or mismatched values. Retain the original
visual evidence separately. The final run validates every actual frequency point
and all four curves; no empty-row termination or assumed coverage is used.

`prepare_native_static_sp` takes exactly `project_id`, `em_job_id`,
`expected_saved_digest`, `snapshot_digest`, `confirm_idle=true`,
`spec`:

```json
{"host_block":"actual-host", "host_pins":[{"pin_name":"...","port_index":0}],
 "expected_nets":[{"name":"actual-net","subnets":[[["Block","actual-host",0],["ExternalPort","P1",0]]]}],
 "diode_blocks":["actual-diode"],
 "control":{"network_pin":2,"probe":"actual-probe","source":"actual-signal-source",
            "bias":"actual-dc-source","ground":"actual-ground","resistance_ohms":50},
 "task":{"task_name":"actual-SP","frequency_unit":"GHz","fmin":1,"fmax":2,
         "samples":3,"port_impedances":{"P1":100,"P2":100}}}
```

This is a schema illustration, **not** a complete circuit or default values:
copy the entire actual `host_pins` and `expected_nets` from native inspection;
all real diode names, task, units, frequency range and port impedances come from
the reviewed project. The supported control chain is host pin → probe → voltage
signal source Ri=50 Ω → voltage DC source Ri=0 Ω → ground, with no unreviewed
parallel branch at the first three links.
Alternatively, use `control={"kind":"resistor_to_ground","network_pin":2,
"resistor":"actual-resistor","resistor_pin":0,"ground":"actual-ground",
"ground_pin":0,"resistance_ohms":50}` for an actual host → 50 Ω resistor →
ground connection. The host-to-resistor net must have exactly those two endpoints;
the ground net may also contain other grounded terminals. The existing native
resistor's `Resistance` and resistance units are read, and its two pin indices
are checked. No voltage, bias or pump source is created for this topology.
Other control topologies are refused.
The two connected measurement ports must already exist; a missing or existing SP leaf is created or updated through the existing Python task API. Missing topology is a specific setup gap,
not a reason to delete a host or issue a solver command. Preparation validates the
current EM/evidence and reviewed topology, records an exclusive before-audit,
zeros supported independent DC and AC/HB source amplitudes, configures and enables
the selected SP leaf, then reads numerical impedances, rechecks untouched topology
and saves. A partial write fences
the session. It does not configure new ports or start a solver. After preparation,
review the actual task sampling in the GUI and create the observation artifact;
GUI evidence is not native sample readback.

`review_native_static_sp` uses the same fields plus `sample_observation={path,sha256}`
and the preparation result's new `saved_digest` and `snapshot_digest`; it is read-only and creates a fresh
impedance receipt. `run_native_static_sp` accepts only `project_id`,
`review_job_id`, `expected_saved_digest`, `confirm_idle=true`, `confirm_run=true`.
It revalidates review, project, EM generation, source, task, impedance and GUI
observation, then executes one selected SP leaf and archives S11/S12/S21/S22.
`read_native_static_sp` accepts `project_id`, `run_job_id`, the post-run
`expected_saved_digest`, explicit positive `positive_run_id`, and
`confirm_idle=true`; it compares the positive-ID data with the archived current
curves. If no unique positive ID exists, retain the archived current curves and
inspect actual IDs; do not rerun to create an ID. `operation_wall_seconds` includes
the service operation and is not solver-only timing. `em_reuse_verified` and
`diode_model_verified` stay false until independent actual-project evidence.

These operations are offline tested, not native acceptance: user authorization,
complete EM evidence, compatible worker, actual idle/GUI review and safety of
any preserved-DE handoff remain required. Do not hot-replace a running worker
or claim the old project's v1/v2 capability implements v3. CST HB remains outside
this path; ADS is responsible for pumped HB.

### Current ordinary-candidate path and minimum gap (2026-11-13)

The requested loop is **same-candidate CST EM → native zero-bias, pump-off
diode SP → ADS pumped bidirectional HB → isolation/insertion-loss analysis →
next candidate**. The user permits a targeted GUI review where the SDK lacks
a reliable getter; a GUI observation must be retained as such, not converted
into a claimed native getter. Measurement excitation stays enabled; the control
termination remains 50 Ω, and only the actual two main-line ports are measured.
CST HB is not authorized by this workflow.

**Published inputs and operations.** Use the protected session's `solve` for
EM, after the engineering contract and current parameter checks pass.
`circuit/build/inspect` can inspect the native schematic, source properties,
ports, nets and tasks; `circuit/build/configure` uses the existing circuit schema
to build supported topology and `configure_nonlinear_model` configures supported
diode models. The existing project-bound `circuit/build/read_sp_impedances`
uses `sp-impedance-read-v1` and takes `task_name`, the actual port-name list and
`confirm_idle=true`; it is not an SP solve. These operations do not by themselves
certify the current EM source, zero-bias diode circuit, sample count or SP result.
The `CircuitResult` Python API reads actual schematic tree paths and explicit run
IDs; archive all four complex curves, units, parameters and source identity.

`prepare_static_sp` is published with `static-sp-prepare-v1`, but is limited to
the documented **embedded Touchstone static-copy topology**, creates new RF
external ports and a task, and is not a general preparation adapter for the
same-project native host block. Do not substitute a self-host deletion: the old
project demonstrated that its automatic host block could not be deleted.
`configure_exploratory_linear_sp` and `run_exploratory_linear_sp` are published,
but their normal gate requires a successful current embedded-network/setup
receipt and supported native sample-count and impedance readbacks; the present
sample-count getter is unsupported. They are not an already accepted native-host
candidate loop. On a bound project, generic `circuit/solve/run_task` is routed
through the bound HB contract, so it is not an authorized escape route for SP.

`run_fenced_static_sp` and `read_fenced_static_sp` are published, tested for a
specific returned **failed preparation** and fence, and require that failed
job plus capture/completion/exclusion and impedance evidence. They are not the
normal successful-EM candidate route. Their shared results logic checks four
task-scoped complex curves and the actual frequency grid after a run, but their
pure-network gate and unchanged 3D inventory requirements do not establish the
behavior of the active native-host circuit.

**Worker and unpublished work.** The engineering session's 2026-11-13 saved
state advertised `static-sp-prepare-v1`, `static-sp-fenced-recovery-v1`,
`static-sp-self-em-exclusion-v1`, `static-sp-guarded-run-v1`,
`static-sp-ready-v1`, `native-static-sp-v1`, and `sp-impedance-read-v1`.
Those are the worker's advertised strings, not proof that a specific method is
registered, loaded or natively accepted. The published `f10bf00` does not
register `review_native_static_sp`, `run_native_static_sp` or
`read_native_static_sp`; similarly named host review/run/read code in a separate
maintenance workspace is **uncommitted and unreleased**. Its tests are offline,
and it assumes an already configured host circuit and SP task; it is not a
complete preparation or an accepted candidate loop. Do not submit it to the
live worker on the strength of an advertised capability string.

For maintenance comparison only, that uncommitted prototype's review input is
`project_id`, `em_job_id`, `expected_saved_digest`, `snapshot_digest`,
`confirm_idle=true`, and `spec` containing `host_block`, `host_pins`,
`expected_nets`, and `task={task_name, frequency_unit, fmin, fmax, samples,
port_impedances}`. Its proposed run input adds a successful `review_job_id`,
the same saved digest and `confirm_run=true`; its proposed read input uses
`run_job_id`, the post-run saved digest and an explicit positive `positive_run_id`.
These describe unfinished source, not currently published operations. The
prototype still requires a separately prepared task and review of sample-count
evidence; its live integration, execution and result identity are not accepted.

The following was the prior gap before the v2 offline implementation: an **owned native-host SP
preparation/review/run/read path** that preserves the existing EM host and diode
connections; checks same-candidate EM generation, complete current connections,
zero external DC and pump, actual source/50 Ω termination, exactly the intended
measurement ports and their impedances; runs only the reviewed SP leaf; then
archives the actual frequency grid and four complex curves with task and run
identity. Reusing the existing configuration, impedance bridge and guarded
run/archive logic is appropriate, but a code splice alone is insufficient:
the existing setup assumes a different topology, native sample-count readback
is unavailable, and the uncommitted host route has not established complete
preparation, source-termination semantics, safe same-project execution, or
native result association. Its intended sample count must be linked to a
reviewable actual GUI/task-setting observation and the resulting full grid
checked after execution; never claim an SDK sample-count getter.

The original session job's `started_at` and `finished_at` provide an attributable
worker-operation wall duration, including its checks and archival, rather than a
pure CST solver time. Obtain solver-only timing from that run's native log when
available and label each duration. Until the v2 host operation is loaded in a compatible safely handed-off worker
and accepted in the actual project, native zero-bias SP and its time are **not computed**. A window showing
idle is useful visual evidence but does not itself authorize a worker handoff or
certify whole-engine idle. Do not replace the active worker for optional status
getters, alter its queue, or attach a second process.

Minimal continuation: (1) the owning session completes and qualifies the
authorized EM; (2) it reviews the real native host, diode wiring, source/load
termination, SP task and actual sampling through available native/GUI evidence;
(3) the missing normal host interface is completed and safely loaded only when
the owning session can accept the required handoff; (4) one leaf SP run is
archived and checked, followed by ADS HB and the requested performance analysis.
No new simulation is authorized by this documentation.

### Recover a returned partial static preparation (offline-tested only)

The owning session reviews the original failed `prepare_static_sp` receipt,
complete current in-memory `circuit.inspect()` snapshot, saved disk digests,
DE/worker identities, dialogs and actual task idle state. Compute `snapshot_digest`
with `cst_automation.workflow.digest(snapshot)`, not the hash of a JSON file.
`begin_failed_static_worker_handoff` takes `failed_job_id`, `project_id`,
`snapshot_digest`, `environment_identity`, `worker_identity`, all registered
`project_digests`, `review_note`, `confirm_idle=true`, and
`accept_unverified_native_handoff=true`. Set `worker_ownership` to `borrowed`
with `confirm_borrowed_worker=true`, or to `owned` with
`confirm_owned_worker=true` and `accept_owned_worker_exit_risk=true`.
Advance using the existing `finish_native_worker_handoff` until complete; it
compares full circuit snapshots on the original DE and returns to the same fence.
The pre-handoff disk digest is not a claim that the dirty circuit was saved.

With the compatible worker advertising `static-sp-fenced-recovery-v1`, submit
`capture_failed_static` with exactly `project_id`, `failed_job_id`,
`expected_disk_digest`, `snapshot_digest` and `confirm_idle=true`. Its new
receipt saves and identifies the reviewed partial state but leaves the fence.
For task inspection submit `inspect_failed_static_task` with exactly
`project_id`, `failed_job_id`, `capture_job_id`, `expected_saved_digest`,
`snapshot_digest`, `expected_task={}` and `confirm_idle=true`. Use its returned
`expected_task` with the same remaining fields in `complete_failed_static_task`.
That operation uses the failed job's original task intent, does not recreate the
task, ports or connections, retains all failure receipts and remains fenced.
Any incomplete or uncertain write is not replayed. Native array binding,
save/attach behavior and this complete chain require in-project acceptance; none
of these operations runs SP or EM. A later run still needs the no-new-EM gate,
actual impedance evidence and the separate protected run/read operation below.

After successful completion, an owning session with worker capability
`static-sp-self-em-exclusion-v1` may submit `exclude_unconnected_self_em` using
exactly `project_id`, `failed_job_id`, `completion_job_id`,
`expected_saved_digest`, `snapshot_digest` (computed from the completion result's
complete `after` snapshot), `block_name`, `confirm_idle=true`, and
`confirm_static_only_copy=true`. If the worker lacks this capability, the owner
must use another reviewed preserved-DE handoff while retaining the fence; the
failed-static handoff accepts `require_self_em_exclusion=true` for this purpose.
The removal compares full available circuit, native 3D solid/parameter and port
inventories, 3D model file bytes and the retained embedded network. It does not
claim complete geometric verification or prove actual solver behavior. On failure
do not replay; retain the partial receipt and re-review the actual scene.

After successful exclusion, submit `read_fenced_static_impedances` with exactly
`project_id`, `failed_job_id`, `exclude_job_id`, `expected_saved_digest`,
`snapshot_digest` of the exclusion result's complete `after` snapshot, and
`confirm_idle=true`. The project-bound ByRef receipt must contain matching native
constant impedances. Its bridge and schematic identity flags retain their original
unverified meaning until independent native acceptance. Both operations retain the
original failure fence and do not solve.

After a successful exclusion and native impedance observation, an owning session
whose worker advertises `static-sp-guarded-run-v1` can submit
`run_fenced_static_sp` with exactly `project_id`, `failed_job_id`,
`exclude_job_id`, `impedance_job_id`, `expected_saved_digest`, `snapshot_digest`
of the excluded circuit, `confirm_idle=true`, and `confirm_run=true`. A further
reviewed preserved-DE handoff may request `require_guarded_static_run=true` if
the current worker is older; it keeps the original fence. The run checks the
actual enabled SP leaf, supported pure-circuit blocks, full source/control and
measurement-port topology, DC-through-band embedded Touchstone, complete
dependencies and the native impedance observation. A changed 3D model inventory
or 3D log is flagged after execution; it is not a claim of absolute process-level
observation. No parent task or 3D solver is submitted. The four result paths are
resolved uniquely from the actual returned task tree. The full current complex
curves and actual grid are archived; common positive IDs are compared to them.
If no unique matching positive ID exists, retain the run and inspect actual IDs;
do not rerun merely to manufacture one.

`read_fenced_static_sp` takes exactly `project_id`, `failed_job_id`, `run_job_id`,
`expected_saved_digest` from the run, an explicitly selected `positive_run_id`,
and `confirm_idle=true`. It reads that actual ID and all four complex curves;
their values, units and stored parameters must match the archived current run.
This content match does not establish that a historical positive ID is immutable
or uniquely attributable to the latest execution. The request does not solve.
Run/read, native task semantics and the positive-ID association are offline-tested
only until the owning project records actual native evidence.

After a successful matching positive-ID read, the owning session can call
`accept_completed_static_recovery` with `failed_job_id`, `run_job_id`,
`read_job_id`, the complete current `project_digests`, the exact
`environment_identity`, `review_note`, and `confirm_idle=true`. The finalizer
rechecks the original failure, saved run and read receipts, raw artifact hashes,
all registered saved files and the native current circuit before setting the
session ready. The original failed job remains failed. Clearing this operational
fence does not accept HB, source qualification, performance, or positive-ID
freshness; the normal engineering gates remain independently required.

### Prepare a dedicated static circuit (new, offline-tested only)

Using the existing owned session submission interface, operation
`prepare_static_sp` takes the following complete `params` structure:

```json
{
  "project_id": "owned-copy",
  "expected_digest": "<saved-project-sha256>",
  "confirm_idle": true,
  "spec": {
    "snapshot_sha256": "<digest-of-complete-native-circuit-inspect>",
    "network_block": "embedded-network-name",
    "network_sha256": "<embedded-touchstone-sha256>",
    "ports": [
      {"name":"P1","position":[0,0],"net_name":"left-net",
       "expected_members":[["Block","embedded-network-name",0],["Probe","left-probe",1]],
       "probe_endpoint":["Probe","left-probe",1]},
      {"name":"P2","position":[100,0],"net_name":"right-net",
       "expected_members":[["Block","embedded-network-name",1],["Probe","right-probe",1]],
       "probe_endpoint":["Probe","right-probe",1]}
    ],
    "task": {"task_name":"StaticSP","frequency_unit":"GHz","fmin":110,"fmax":170,
             "samples":61,"port_impedances":{"P1":100,"P2":100}},
    "control": {"network_pin":2,"probe":"control-probe","source":"pump-source",
                "bias":"bias-source","ground":"ground-block","resistance_ohms":50}
  }
}
```

Names, coordinates, pin indices, frequencies and impedances above are schema
illustrations only. Populate them from the actual native review, never copy them
as defaults. The snapshot hash is `cst_automation.workflow.digest(snapshot)` of
the **complete current** `app.circuit.inspect()` result. The project must be
saved, idle, already open on its owning worker, with `static-sp-prepare-v1`.
Existing external ports or same-named task are rejected; this first version is
for a static-dedicated circuit with two probe-coupled RF sources and a serial
voltage-signal/voltage-DC/ground control branch. Its three control nets must have
only their two expected endpoints; resistance is read from native source Ri and
simple native parameter references in Ohm. Other source classes are rejected.

Before modifying, the worker checks all native blocks, source properties, net
and subnet membership, exact control path and resistance, saved project and
embedded payload hashes, and dependency inventory. It stores an exclusive
`static_sp_prepare/<job_id>.before.json` before any write. Then it zeroes all
supported DC and signal AC/HB amplitudes, creates two external ports, attaches
them before disconnecting the RF probes, and creates a new SP task. It checks
the untouched diode/block data, RF and control networks, source impedances,
dependency and payload hashes; it saves only after native preparation returns.
Each partial/unknown failure is fenced and is never automatically replayed.
The original dynamic circuit is preserved in the separately archived source,
not restored in this static-only copy.

Task frequency limits/units and port impedance modes are read back. The source
type getter is unsupported for the native SP task and is not queried. Sample count and
constant impedance values remain `unsupported` in this prepare receipt; use the
owned `read_sp_impedances` bridge for a separate native check. Isolated source
branches, ByRef array binding, real solver behavior and four-result coverage are
not certified by preparation. This build operation does not run SP or EM; use the
separate protected static run/read path only when all of its evidence is present.

Existing `configure_exploratory_linear_sp` intentionally refuses setup when native
sample-count and constant-impedance readback are unsupported. Its current path
also creates new external ports and a new task, so it is not an adapter for the
existing diode circuit and task. CST 2026 DES SimulationTask help documents
`GetConstPortImpedance(name, real&, imaginary&)`; the Python ByRef return convention
is unverified. Its SP property list does not specify a sample-count getter. Do not
guess the tuple shape or property key and do not remove the protected preflight.
Connection/source/diode state, zero external bias/pump, native task identity, exact
EM payload, S11/S22/S21/S12 complex result identity and all frequency samples still
need a supported reviewed implementation and native acceptance before use.

The low-level `inspect_existing_linear_sp(schematic, task_name, ports)` now reads
documented task properties, units and port modes on an already owned schematic.
It is not exposed in the guarded session queue and does not validate impedance
values, sample count, diode operating point or native job association. The existing
SDK-free `sp_impedance_bridge` constructs and parses a project-bound ByRef VBA
receipt, but its native execution and schematic identity are still unverified.

The owned worker can request the following using the existing
`submit_cst_session_operation` or `SessionManager.submit`, operation `circuit`:

```json
{"project_id":"owned-project","kind":"build","settings":{"operation":"read_sp_impedances","task_name":"SP task","ports":["P1","P2"],"confirm_idle":true}}
```

Use actual task and all relevant port names, not these illustrative names. The
worker must advertise `sp-impedance-read-v1` and hold the already-open project;
the request never launches a worker, reopens a tab, saves or solves. The raw and
request receipts remain in the session's `sp_impedance_queries` directory.
The return's idle and schematic identity are not independently verified. Its
purpose is scoped native bridge verification by the owner; it does not activate
the existing setup or solve gate and does not prove zero bias/pump.

`circuit` build `inspect` on a worker advertising
`circuit-source-property-readback-v1` enumerates properties and units of supported
native DC/signal voltage/current source blocks. The official DES block help names
`DC`, `ACAmplitude`, `HBAmplitude` and `Ri` for the respective voltage sources;
record the actually enumerated properties and parameter expressions rather than
assuming their values. Failure appears in `unknown`. Independent native source
readback, connectivity and effective zero excitation must be reviewed before any
static SP; requested zero values or source type alone cannot prove it. This getter
has offline tests only. It does not change a bias/pump source or restore HB state.

Before adding a measurement ExternalPort, explicitly map each RF/bias/pump source,
its connected net and internal impedance, each measurement port, and each load.
Zero source amplitude alone leaves the source impedance in circuit; check whether
that impedance remains in parallel with the new port's reference impedance. Do not
remove a source and silently leave a net floating, or declare the termination
correct from amplitude alone. Review the actual topology, net membership, source
properties and effective termination as a single circuit. Preserve original 3D
ports, EM payload and diode wiring; an authorized static adaptation is reused on
subsequent candidates with unchanged circuit topology, not rebuilt every round.
The preparation operation above checks only its documented serial topology;
other topologies and solver behavior still require separate native evidence.

Official CST 2026 `VBA_DES/special_vbacommands/net_object.htm` documents
`Net.RemoveComponentPorts(componentports, netname)`, `AddComponentPorts`, and
`AddToSubnet`; these are candidate primitives for deliberate source isolation and
restoration. Removing a port removes it from its net, and adding a port already
connected elsewhere moves it from that net. A safe transaction must retain full
net/subnet membership, remove only reviewed source endpoints, independently read
all nets after every mutation, explicitly retain the required control termination,
and fence partial/unknown failures without replay. Restoration is required if the
same circuit is to be reused dynamically; the documented preparation operation is
instead limited to a user-authorized static-only copy. Python ByRef array behavior
and native restoration have not yet been verified. These primitives do not permit
bypassing the session's protected execution path.

## Saved copy and history evidence

The installed Python CST interface documents `Project.save(path, include_results=True,
allow_overwrite=False)`, and the repository `app.save_as` delegates to that method.
The native DES `Project.SaveAs(filename, include_results)` also documents inclusion
of results. These statements do not certify a complete companion, external links,
historical run association, lock exclusion, or safe behavior on an active session.
No protected session-level save-copy operation has been verified here. An ordinary
file copy of a `.cst` alone is not an archive with complete historical results.
Before accepting an authorized copy, the owning session must verify native saved
identity and project/required companion contents, preserve necessary dependencies,
check all needed result tree entries and positive IDs against stored parameter
combinations on the copy, and keep the source untouched. Active CST root Model.lok
is a temporary exclusive lock, not copied as result data; omission does not prove
any other file is safe to omit. Never copy an unstable set and call it complete.
No close/reopen or solver is authorized by this description.
