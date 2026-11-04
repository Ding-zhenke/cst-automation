# CST API offline repairs

Goal: reduce UI dependence using documented commands and explicit evidence, without accessing CST.

Scope: the six issues in the delegated request; no device data or live processes.
Use the existing checkout. Implement inline with failing regression tests first.

- [x] Fix DiscretePort commands and coordinate selection using installed 2026 help.
- [x] Preserve decoration evidence, exclude only proven empty noninteractive glow windows; retain unknown failures.
- [x] Add process creation identity and explicit acknowledgement of a completely read, unchanged known error. A click never means recovery.
- [x] Add host desktop preflight and checked session entry; IPC and machine idleness remain unknown until separately verified.
- [x] Provide explicit VBA target adapters and documented CircuitProbe/Net macro builders; never trial native methods.
- [x] Report computation and convergence separately; no invented continue API or quiet-mode workaround.
- [x] Run offline suite; document examples, sources and native acceptance gaps.

Evidence: installed Online Help under CST Studio Suite 2026, VBA_3D DiscretePort,
MeshAdaption3D, FDSolver; VBA_DES CircuitProbe/Net; Python cst.interface.
Continuation ruling: no explicit public CONTINUE selector found in those sources.
Do not expose a method claiming mesh continuation until native verification is possible.

Result: 504 passed, 2 skipped (MCP extra unavailable), 1 GUI deselected.
Native tests deliberately deferred. See docs/VALIDATION.md and the API repair guide.
Additional reported connect/pause/abort gaps are documented, not claimed fixed.
