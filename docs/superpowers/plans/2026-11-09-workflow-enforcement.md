# Parameter → EM → HB Enforcement Implementation Plan

> **For agentic workers:** implement sequentially in this session; the user has already approved the design and implementation.

**Goal:** Reject incomplete or conflicting engineering requests at the actual service boundary without touching live simulations.
**Architecture:** Immutable project-bound contracts, submit/execution checks, native readback, durable EM-linked analysis evidence, and worker capability negotiation.
**Tech Stack:** Existing Python session queue, JSON records, pytest, existing plugin builder.
**Spec:** `docs/PUBLIC_API.md`, Mandatory parameter → EM → HB workflow contracts.

## Global Constraints

- Never restart or modify a live CST worker/project; all verification uses isolated fixtures.
- No domain geometry or private device parameters in the general package.
- No user-global MCP configuration changes; explicit CLI/MCP registration.
- Publish only tested generic implementation and documentation on main.

## Review Focus

- Parameter aliases and expressions cannot evade fixed/range restrictions.
- Queue-time approval cannot survive a changed spec, input generation or artifact.
- Rejected requests must not launch a worker, acquire an app or invoke a solver.
- Older workers cannot accept guarded work; read-only status and old receipts remain available.
- Failed parameter mutations invalidate downstream evidence without claiming rollback.

## Tasks

- [x] Add failing contract/session tests, including a valid chain and zero native calls on rejection.
- [x] Implement pure contract normalization and comparisons in `cst_automation/workflow.py`.
- [x] Implement binding, evidence and native guards in `tpc_service/sessions/workflow.py`; integrate manager, operations and worker.
- [x] Expose binding through session CLI/MCP; fence legacy temporary service routes.
- [x] Test stale queued work, failure classification, artifact changes, fixed parameters and old workers.
- [x] Update skills, guide and plugin; run targeted and complete offline checks.
- [x] Independently review the completed diff, build/install the plugin, commit and push main.

## Verification record

- 40 focused enforcement cases passed, including CLI/MCP, malformed requests, stale evidence and failed writes.
- Independent review found three input-timing/routing issues; fixed and re-reviewed without remaining must-fix findings.
- Live CST access and worker restart were not performed. Native acceptance remains pending.
