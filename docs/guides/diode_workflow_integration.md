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
This requirement is an acceptance contract; no automated topology/termination
validator or source-isolation transaction is implemented yet.

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
