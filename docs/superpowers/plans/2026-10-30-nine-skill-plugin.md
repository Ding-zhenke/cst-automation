# Nine-skill CST Plugin Implementation Plan

> **For agentic workers:** Use superpowers:executing-plans. User approved implementation in this chat; proceed without another approval checkpoint.

**Goal:** Deliver a portable, model-free plugin containing the nine approved CST skills.

**Architecture:** Keep instruction sources in root skills/. Package explicit files with a standard-library builder. Use focused local references and one shared plotting style; keep the Python runtime separate.

**Tech Stack:** Markdown, YAML, JSON, Python standard library, pytest, optional Matplotlib, Codex plugin CLI in an isolated home.

**Spec:** ../specs/2026-10-30-nine-skill-plugin-design.md

## Global Constraints

- Nine approved skills only; no private project/model files or machine paths.
- Preserve private installed skills and unrelated primary-checkout changes.
- No CST launch/solve, automatic dependency installation or global plugin configuration edits.
- Sync parameter-study contracts from the owning current workspace, with capability checks.

## Review Focus

- Unlisted files must not enter the archive; explicitly listed private paths/numbers must fail validation.
- Relative reference and asset links must remain inside the standalone archive and resolve.
- Archived study data and current run aliases must not be confused.
- Device metrics must account for RF/LO/IF and switching states instead of forcing two-port same-frequency plots.
- Compatibility manifests and runtime availability must be represented honestly.

## Tasks

- [x] Task 1: Add packaging/privacy/link tests, observe baseline failures, then implement scripts/build_plugin.py and explicit package file declarations. Test stable archives, input rejection, no unlisted files and no source mutation.
- [x] Task 2: Rewrite six portable core entries and add diode-loading, device-characterization and figures sequentially. Add focused references and style asset; test each entry and all links. Sync EM/circuit study semantics from the current owning code without copying model data.
- [x] Task 3: Complete docs/manifests, build ZIPs, run tests and skill application trials, inspect with a fresh reviewer, and test discovery/installation using an isolated Codex home. Hash private sources before/after. Commit only this branch's plugin work and deliver artifacts plus verification evidence.

## Progress

- Baseline skill trial: six entries lack generic package-parasitic ownership, mixer cross-frequency metrics, and scientific plotting contracts. No CST operations performed.
- Isolation ruling: use a separate local Git copy under work/ because all development artifacts must stay in this repository and the primary checkout has unrelated active edits.
- Initial package tests failed for the missing three entries, builder, style and study reference; final focused/public API checks pass (26 tests).
- Application trials cover generic switch loading, mixer conversion metrics, supplied-data plotting, archived HB/EM studies and negative triggers. Index omission found and corrected.
- Host marketplace installation and skills/list in an isolated home discover exactly nine prefixed skills with no errors. No model turn or CST access is used.
- Private original skill directories have 16 files; hashes remain unchanged.
- Review: no blocking findings. Plugin sources are distributed separately from the Python sdist, which retains its existing packaging contract.
- Final review confirms the additional Chinese-adjacent quantity, leading-decimal quantity and UNC-path regression checks. Separate source ZIP rebuilds the identical plugin archive.
