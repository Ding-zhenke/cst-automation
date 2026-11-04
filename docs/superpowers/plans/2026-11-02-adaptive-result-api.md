# Adaptive result API implementation plan

Goal: merge explicitly supplied modeler paths with offline results paths and read
complex S versus mesh pass without confusing them with frequency sweeps.

Use the current branch/checkout; preserve prior edits. No CST connections, native
operations or device data. Implement inline with injected boundaries and TDD.

- [x] Document public signatures and evidence/normalization boundaries first.
- [x] Add failing tests for source merging/failure, missing-tree-but-readable
      paths, explicit run selection, Pass-axis validation and normalization.
- [x] Add focused adaptive result mixin, attach it to Result, isolate ordinary
      frequency-tree discovery from adaptive paths.
- [x] Verify no implicit SDK/session operations in the new methods; run offline
      regressions with test artifacts under work/.
- [x] Document examples and offline validation; retain native acceptance as pending.

Files: cst_solver/adaptive_results.py owns enumeration and Pass decoding;
cst_solver/_result_core.py integrates the mixin and ordinary S filtering;
cst_solver/tests/test_adaptive_results.py injects modeler/results boundaries;
docs/PUBLIC_API.md and docs/guides/api-offline-repairs.md describe the contract.
