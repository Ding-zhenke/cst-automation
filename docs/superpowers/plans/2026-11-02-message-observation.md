# Message observation repair

User authorized implementation and push. Use current branch; include prior
authorized API changes from this chat. No CST, SDK probes, native project reads,
global environment changes or deployment. Reuse repository .venv.

- [x] Inspect run_checked -> RunContract -> backend/service/MCP propagation.
- [x] Update public API contract before code changes.
- [x] Add failing offline tests for not-read/read/read-failed, partial generators,
      explicit caller evidence, JSONL and backend/service/MCP propagation.
- [x] Implement minimal state handling; keep native/mesh/log evidence independent.
- [x] Run regressions and fresh review; update evidence and examples.
- [x] Prepare all authorized changes from this chat for commit/push on the dedicated branch.

Verification: 572 passed, 2 MCP skipped, 1 GUI excluded. Fresh review's save-failure
evidence finding was reproduced, fixed, regression-tested and confirmed resolved.
Commit/push outcome is reported in the delivery message, not assumed from preparation.
