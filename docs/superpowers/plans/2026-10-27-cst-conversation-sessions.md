# CST conversation sessions implementation plan

> **For agentic workers:** Use superpowers:executing-plans inline. Follow test-first steps and record evidence in work/session_validation/progress.md.

**Goal:** Isolate each conversation's CST environment, preserve it across client disconnects, and resume without replaying uncertain writes.
**Architecture:** A local manager client routes authenticated requests to one persistent worker process per session. The durable manager registry and per-session queues live under an explicit work root; worker SDK operations stay on one thread. The manager facade needs no additional daemon: OS file locks protect its durable registry and workers outlive clients.
**Tech Stack:** Python standard library, existing CST SDK, existing circuit handlers, pytest.
**Spec:** ../specs/2026-10-27-cst-conversation-sessions-design.md

## Global constraints

- Keep current checkout and .venv; no global configuration or dependency changes.
- No automatic arbitrary-DE attach; exact process identity and project identity are mandatory.
- No automatic replay of uncertain mutations or existing running jobs.
- Public API documented before cross-package implementation; explicit MCP registration.
- No geometry without preview approval; initial native checks use empty environments only.
- Preserve legacy temporary RunService behavior.

## Review focus

- DE creation succeeded but process identity receipt was lost: block and reconcile, never relaunch blindly.
- PID reused or manual active-tab switch: reject mismatched process and use explicit project handles.
- Client dies after submission: stable request IDs recover receipts without executing twice.
- Close arrives during queued work: drain accepted work; reject later writes and persist close failure.
- Path aliases, duplicate binding and concurrent launch: lock actual roots and prevent a second writer.

### Task 1: Native feasibility and protocol

- [x] Preserve doctor JSON; run detached empty-DE process and read its status from a later shell call.
- [x] Disconnect SDK owner and reconnect by recorded PID; verify full OS identity, close only test DE.
- [x] Record actual evidence and failures without inferring solver or geometry success.
- [x] Add persistent session contract to docs/PUBLIC_API.md.

### Task 2: Durable manager and isolated workers

Files: tpc_service/sessions/{store,manager,worker,native}.py, tpc_service/tests/test_sessions.py.
Interfaces: SessionManager(root).ensure(binding, request_id), status(session_id, credential),
submit(session_id, credential, request_id, operation, params), job(...), resume(...), close(...).

- [x] Test binding idempotency, credential isolation, same-name projects, request conflicts, worker launch races, and real subprocess survival with a fake SDK boundary. Watch failures before implementing.
- [x] Implement atomic files, OS locks, explicit process identities, durable queue/receipts and detached per-session worker.
- [x] Add session-owned app reuse, exact reattachment, launch_intent and needs_reconcile states.
- [x] Test restart/death and duplicate requests; read-only status never launches CST.

### Task 3: CST operations and MCP integration

Files: sessions/operations.py, cst_mcp/session_tools.py, cst_mcp/__main__.py, skills/*, tests.
Interfaces: explicit persistent-session MCP tools with session_id, credential, request_id; no global active session.

- [x] Test project creation/import once, ordered modeling stages, checkpoints and uncertain-stage fencing, explicit close/drain semantics.
- [x] Implement a bounded explicit operation registry; reuse circuit handlers with a borrowed app, existing checked solver, and safe geometry commands after preview.
- [x] Test MCP schemas/dispatch and capability discovery; register persistent tools explicitly without changing legacy tools.
- [x] Add command-line client/startup and recovery instructions; avoid changing user MCP config.

### Task 4: Verification and delivery

- [x] Run focused tests and whole offline pytest suite; preserve logs.
- [x] Run native empty-environment reuse, precise reconnect, and explicit-close checks against only test sessions.
- [x] Independently review final code; fix material findings test-first.
- [x] Update docs/VALIDATION.md with separate offline/process/DE/readback/solver evidence and remaining limitations.
- [x] Present changes and exact verification; no push without user instruction.

Plan ruling: execute now under the user's explicit authorization; no additional plan approval gate.
