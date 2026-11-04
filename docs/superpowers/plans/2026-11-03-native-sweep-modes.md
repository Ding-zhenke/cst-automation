# Native Parameter Sweep Modes Implementation Plan

> For agentic workers: use superpowers:executing-plans, one task at a time.

**Goal:** expose native linear/logarithmic ranges and existing primitive APIs through owned sessions.
**Architecture:** keep validation/serialization in simulation/sweep.py; retain explicit session routing and configuration-only scope.
**Tech stack:** Python, pytest, official CST 2026 AddParameter_Samples contract.
**Spec:** user's 2026-11-03 request to support linear/logarithmic sampling and assess missing API/skill coverage.

## Global constraints
- Preserve unrelated existing edits; do not change global environments or TPC migration sources.
- Keep legacy linear calls and discrete sweep definitions compatible; never invoke a solver from configuration.
- Keep project parameters out of shared skills/examples.

## Review focus
- Zero and negative logarithmic bounds are rejected before mutation.
- Counts mean samples including endpoints, not intervals.
- A bad later axis cannot leave a partly replaced sequence.
- Native sampling modes remain visible instead of being flattened into arbitrary points.
- API existence, routed access, native readback and solver results remain separate evidence.

## Task 1: API and session integration
- [x] Write regression tests and observe expected missing-interface failures (18 failures).
- [ ] Add logarithmic flag, mixed range/list schema, explicit primitive routes and type stubs.
- [ ] Run focused tests and repository regression checks.
- [ ] Update authoritative docs/skills and assess the installed plugin separately.
- [ ] Check the approved project's F mesh settings without running its solver.
