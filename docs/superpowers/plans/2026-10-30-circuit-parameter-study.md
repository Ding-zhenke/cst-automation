# Circuit Parameter Study Implementation Plan

> **For agentic workers:** Use superpowers:executing-plans to implement task by task.

**Goal:** 通用电路参数序列、EM 依赖与可比较的历史归档。
**Architecture:** 纯数据校验 → CircuitAPI 编排现有求解器 → StudyResult 归档/查询；服务/MCP 仅路由。
**Tech Stack:** Python >=3.9, pathlib/json/csv, pytest, existing CST native objects.
**Spec:** docs/superpowers/specs/2026-10-30-circuit-parameter-study-design.md

## Global Constraints
不改拓扑，不启动设备求解，不降低运行证据；每批次唯一命名；保留现有修改。先更新 PUBLIC_API。原生单位明确，元件属性通过现有 SI 转换；EM 每点重算，不声称缓存已验收。

## Review Focus
非法后续工况不能在早期点开始后才发现；相同参数重跑不能覆盖；电路成功但 EM 未验证必须停止；未知单位与不一致参数不得比较；结果写回和来源查询必须保留复数与单位。

### Task 1: Schema and archive
Files: cst_automation/circuit_studies.py, cst_solver/circuit/study_results.py, tests/test_circuit_studies.py.
Interfaces: normalize_parameter_study(spec)->dict; StudyResult(batch_path).list_cases(parameters=None), read_curve(case_id,result_name), compare(result_name,parameters=None,component='magnitude'), verify_project().
- [x] Write tests for schema validation, append-only case snapshots, complex CSV, filters, comparison unit mismatch and saved native readback.
- [x] Run targeted pytest; confirm missing new modules (RED).
- [x] Implement pure validation and archive/query operations.
- [x] Run targeted tests to GREEN.

### Task 2: Execution
Files: cst_solver/circuit/study.py, api.py, __init__.pyi, tests/test_circuit_study_run.py.
Interface: CircuitAPI.run_parameter_study(spec)->dict; archive path is derived from saved project, not caller-selected output.
- [x] Write tests for whole-plan preflight, EM-before-circuit, repeated points, partial failures and unique result leaves.
- [x] Run to RED, implement orchestration, run to GREEN.

### Task 3: Service, MCP and usage
Files: tpc_service/circuit.py, cst_mcp/circuit_tools.py, their existing test files, docs/PUBLIC_API.md, docs/guides/circuit_parameter_studies.md, docs/VALIDATION.md, skills/cst-circuit/SKILL.md, skills/cst-results/SKILL.md.
- [x] Test invalid study rejection before SDK, worker route and MCP queue.
- [x] Implement additive routes run_parameter_study / run_circuit_parameter_study.
- [x] Document general examples, results locations, native-unit and result storage limits.
- [x] Run affected regression tests, review changes, fix verified defects, record final status.

## Execution record
Native execution in existing non-main feature checkout; no new worktree because current uncommitted solver/API fixes are part of the baseline. Preserve all prior changes and do not commit unrelated files. User already authorized execution; no further plan approval requested.

Final verification: 874 passed, 2 deselected, 9 existing warnings. Independent review found 3 Important issues; all reproduced and fixed in one pass, with final green full suite. Native solver/reopen acceptance not executed.
