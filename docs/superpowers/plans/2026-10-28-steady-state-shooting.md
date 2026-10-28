# Steady State shooting configuration

User requested the documented CST periodic steady-state feature as a reusable library API.
Add configure_steady_state_task(task_name, settings, create=False), separate from ordinary
transient integration/source configuration. Support automatic period detection, unit-explicit
manual period and optional relative shooting tolerance. Configure and read back only; no
save, solver submission, SDK discovery or model changes in the Python facade.

1. Document protocol; add failing offline tests for validation, local units, conflict handling,
   property readback, partial failure, service worker/save behavior and MCP queue routing.
2. Implement pure normalization, facade/adapter and explicit service/MCP registrations.
3. Update stubs, guides, skill and validation boundaries. Run relevant tests, then repository
   offline regression and package build. Preserve pre-existing session-readback edits.

CST 2026 source: SimulationTask object / transient properties; Steady State Simulation and
Solver Settings for Steady State Simulation. No private model values enter generic docs.
