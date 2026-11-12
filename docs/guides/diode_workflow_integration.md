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
actual impedance evidence and a separate protected run/read implementation.

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
not certified by preparation. This build operation does not run SP or EM; a
separate protected static run/read path is still being implemented. Until it is
available, do not bypass the workflow or claim completed SP.

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
