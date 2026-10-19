# 文件迁移与归属映射

来源代码在只读快照创建前读取自 `D:\成电博士生涯\自动建模算法尝试\TPC`，HEAD `51e4a63d302f0deea58d2a2df349892087dbdfe7`。快照压缩包和 SHA-256 清单位于忽略目录 `work/source-snapshot/`，未公开。表中“改写”项保留目标 API/行为，但切断领域依赖。

## 逐文件去向

| 源相对路径 | 本仓库路径 | 处理 |
|---|---|---|
| `—` | `skills/README.md` | repository skill index |
| `—` | `skills/cst-diagnostics/SKILL.md` | new focused repository skill |
| `—` | `skills/cst-modeling/SKILL.md` | new focused repository skill |
| `—` | `skills/cst-results/SKILL.md` | new focused repository skill |
| `—` | `skills/cst-simulation/SKILL.md` | new focused repository skill |
| `—` | `AGENTS.md` | updated repository rules for active migration |
| `LICENSE` | `LICENSE` | copied MIT license and copyright |
| `—` | `README.md` | rewritten for standalone package |
| `—` | `cst_automation/__init__.py` | new public namespace |
| `tpc_toolkit/curves.py` | `cst_automation/curves.py` | moved to shared namespace |
| `—` | `cst_automation/py.typed` | new typing marker |
| `tpc_toolkit/s2p.py` | `cst_automation/s2p.py` | moved to shared namespace |
| `—` | `cst_solver/guards.py` | public façade for the stable guard API; `_guards.py` stays internal |
| `integrations/cst-mcp/src/cst_mcp/__init__.py` | `cst_mcp/__init__.py` | rewritten exports for generic MCP API |
| `integrations/cst-mcp/src/cst_mcp/__main__.py` | `cst_mcp/__main__.py` | moved to root package |
| `integrations/cst-mcp/src/cst_mcp/analysis.py` | `cst_mcp/analysis.py` | adapted to cst_automation.curves |
| `integrations/cst-mcp/src/cst_mcp/errors.py` | `cst_mcp/errors.py` | moved to root package |
| `integrations/cst-mcp/src/cst_mcp/isolation.py` | `cst_mcp/isolation.py` | moved to root package |
| `integrations/cst-mcp/src/cst_mcp/reporting.py` | `cst_mcp/reporting.py` | rewritten report renderer; remove topo_modeler dependency |
| `integrations/cst-mcp/src/cst_mcp/runtime.py` | `cst_mcp/runtime.py` | adapted env naming; legacy env accepted |
| `integrations/cst-mcp/src/cst_mcp/server.py` | `cst_mcp/server.py` | adapted server name and tool annotations |
| `integrations/cst-mcp/src/cst_mcp/tools.py` | `cst_mcp/tools.py` | rewritten as generic tools plus explicit extension API |
| `cst_solver/__init__.py` | `cst_solver/__init__.py` | copied |
| `cst_solver/__main__.py` | `cst_solver/__main__.py` | copied |
| `cst_solver/_dialog_uia.py` | `cst_solver/_dialog_uia.py` | copied |
| `cst_solver/_guards.py` | `cst_solver/_guards.py` | copied |
| `cst_solver/_path_tools.py` | `cst_solver/_path_tools.py` | copied |
| `cst_solver/_result_core.py` | `cst_solver/_result_core.py` | copied |
| `cst_solver/config.py` | `cst_solver/config.py` | copied |
| `cst_solver/config_template.py` | `cst_solver/config_template.py` | copied |
| `cst_solver/dialogs.py` | `cst_solver/dialogs.py` | copied |
| `cst_solver/environment.py` | `cst_solver/environment.py` | copied |
| `cst_solver/expressions.py` | `cst_solver/expressions.py` | copied |
| `cst_solver/failures.py` | `cst_solver/failures.py` | copied |
| `cst_solver/import_export/__init__.py` | `cst_solver/import_export/__init__.py` | copied |
| `cst_solver/import_export/io.py` | `cst_solver/import_export/io.py` | copied |
| `cst_solver/material/__init__.py` | `cst_solver/material/__init__.py` | copied |
| `cst_solver/material/materials.py` | `cst_solver/material/materials.py` | copied |
| `cst_solver/mesh/__init__.py` | `cst_solver/mesh/__init__.py` | copied |
| `cst_solver/mesh/mesh.py` | `cst_solver/mesh/mesh.py` | copied |
| `cst_solver/modeling/__init__.py` | `cst_solver/modeling/__init__.py` | copied |
| `cst_solver/modeling/booleans.py` | `cst_solver/modeling/booleans.py` | copied |
| `cst_solver/modeling/curves.py` | `cst_solver/modeling/curves.py` | copied |
| `cst_solver/modeling/curves_ops.py` | `cst_solver/modeling/curves_ops.py` | copied |
| `cst_solver/modeling/picks.py` | `cst_solver/modeling/picks.py` | copied |
| `cst_solver/modeling/primitives.py` | `cst_solver/modeling/primitives.py` | copied |
| `cst_solver/modeling/transforms.py` | `cst_solver/modeling/transforms.py` | copied |
| `cst_solver/modeling/wcs.py` | `cst_solver/modeling/wcs.py` | copied |
| `cst_solver/parameters.py` | `cst_solver/parameters.py` | copied |
| `cst_solver/postprocessing/__init__.py` | `cst_solver/postprocessing/__init__.py` | copied |
| `cst_solver/postprocessing/farfield.py` | `cst_solver/postprocessing/farfield.py` | copied |
| `cst_solver/postprocessing/plot.py` | `cst_solver/postprocessing/plot.py` | copied |
| `cst_solver/postprocessing/proc.py` | `cst_solver/postprocessing/proc.py` | copied |
| `cst_solver/postprocessing/result_export.py` | `cst_solver/postprocessing/result_export.py` | copied |
| `cst_solver/project.py` | `cst_solver/project.py` | copied |
| `—` | `cst_solver/py.typed` | new typing marker |
| `cst_solver/run_contract.py` | `cst_solver/run_contract.py` | copied |
| `cst_solver/setup.pyi` | `cst_solver/setup.pyi` | copied |
| `cst_solver/simulation/__init__.py` | `cst_solver/simulation/__init__.py` | copied |
| `cst_solver/simulation/boundary.py` | `cst_solver/simulation/boundary.py` | copied |
| `cst_solver/simulation/monitors.py` | `cst_solver/simulation/monitors.py` | copied |
| `cst_solver/simulation/ports.py` | `cst_solver/simulation/ports.py` | copied |
| `cst_solver/simulation/setup.pyi` | `cst_solver/simulation/setup.pyi` | copied |
| `cst_solver/simulation/solver.py` | `cst_solver/simulation/solver.py` | copied |
| `cst_solver/simulation/sources.py` | `cst_solver/simulation/sources.py` | copied |
| `cst_solver/tests/data/expected_port_vba.json` | `cst_solver/tests/data/expected_port_vba.json` | copied |
| `cst_solver/tests/test_dialog_windows.py` | `cst_solver/tests/test_dialog_windows.py` | copied |
| `cst_solver/tests/test_environment.py` | `cst_solver/tests/test_environment.py` | copied |
| `cst_solver/tests/test_expressions.py` | `cst_solver/tests/test_expressions.py` | copied |
| `cst_solver/tests/test_failures.py` | `cst_solver/tests/test_failures.py` | copied with TPC-specific test cases removed |
| `cst_solver/tests/test_farfield_export.py` | `cst_solver/tests/test_farfield_export.py` | copied |
| `cst_solver/tests/test_guards.py` | `cst_solver/tests/test_guards.py` | copied |
| `cst_solver/tests/test_material_color.py` | `cst_solver/tests/test_material_color.py` | copied |
| `cst_solver/tests/test_material_dispersion.py` | `cst_solver/tests/test_material_dispersion.py` | copied |
| `cst_solver/tests/test_picks.py` | `cst_solver/tests/test_picks.py` | copied |
| `cst_solver/tests/test_port_orientation_guard.py` | `cst_solver/tests/test_port_orientation_guard.py` | copied |
| `cst_solver/tests/test_ports_vba.py` | `cst_solver/tests/test_ports_vba.py` | copied |
| `cst_solver/tests/test_reported_bugfixes.py` | `cst_solver/tests/test_reported_bugfixes.py` | copied |
| `cst_solver/tests/test_result_items.py` | `cst_solver/tests/test_result_items.py` | copied |
| `cst_solver/tests/test_result_open.py` | `cst_solver/tests/test_result_open.py` | copied |
| `cst_solver/tests/test_run_contract.py` | `cst_solver/tests/test_run_contract.py` | copied |
| `cst_solver/tests/test_session_lifecycle.py` | `cst_solver/tests/test_session_lifecycle.py` | copied |
| `cst_solver/tests/test_vba_specs.py` | `cst_solver/tests/test_vba_specs.py` | copied |
| `cst_solver/tests/test_view_capture.py` | `cst_solver/tests/test_view_capture.py` | copied |
| `cst_solver/units.py` | `cst_solver/units.py` | copied |
| `cst_solver/validation.py` | `cst_solver/validation.py` | copied |
| `cst_solver/vba_specs.py` | `cst_solver/vba_specs.py` | copied |
| `—` | `docs/INSTALLATION.md` | new independent installation guide |
| `—` | `docs/PUBLIC_API.md` | new cross-package contract |
| `—` | `docs/SPLIT_PLAN.md` | new approved implementation plan and execution record |
| `docs/guides/cst_dialogs.md` | `docs/guides/cst_dialogs.md` | copied dialog guide |
| `docs/guides/cst_environment.md` | `docs/guides/cst_environment.md` | copied environment guide |
| `—` | `docs/guides/mcp-usage.md` | new MCP guide |
| `—` | `docs/guides/python-usage.md` | new usage guide |
| `—` | `docs/guides/troubleshooting.md` | new troubleshooting guide |
| `docs/packages/cst_solver.md` | `docs/packages/cst_solver.md` | copied API reference |
| `—` | `pyproject.toml` | new cst-automation packaging config; no old monorepo config copied |
| `tpc_service/__init__.py` | `tpc_service/__init__.py` | copied |
| `tpc_service/backends/__init__.py` | `tpc_service/backends/__init__.py` | copied |
| `tpc_service/backends/base.py` | `tpc_service/backends/base.py` | copied |
| `tpc_service/backends/cst_backend.py` | `tpc_service/backends/cst_backend.py` | rewritten; remove topology branches, keep generic solve |
| `tpc_service/backends/fake.py` | `tpc_service/backends/fake.py` | copied |
| `tpc_service/errors.py` | `tpc_service/errors.py` | copied |
| `tpc_service/registry.py` | `tpc_service/registry.py` | copied |
| `tpc_service/service.py` | `tpc_service/service.py` | copied |
| `tpc_service/state.py` | `tpc_service/state.py` | copied |
| `tpc_service/store.py` | `tpc_service/store.py` | copied |
| `tpc_service/tests/test_cst_backend_offline.py` | `tpc_service/tests/test_cst_backend_offline.py` | rewritten for generic backend contract |
| `tpc_service/tests/test_dialog_monitoring.py` | `tpc_service/tests/test_dialog_monitoring.py` | copied |
| `tpc_service/tests/test_service.py` | `tpc_service/tests/test_service.py` | copied |
| `tpc_service/tests/test_state.py` | `tpc_service/tests/test_state.py` | copied |
| `tpc_service/tests/test_store_registry.py` | `tpc_service/tests/test_store_registry.py` | copied |
| `tpc_service/tests/test_worker_serial.py` | `tpc_service/tests/test_worker_serial.py` | copied |
| `tpc_service/worker.py` | `tpc_service/worker.py` | copied |

## 排除与不迁移

- `topo_modeler/`、`topo_templates/`、`mesh_grid/`、旧 `templates/` shim 和其测试归 TPC；本仓库无其代码或运行依赖。
- `tpc_toolkit/ga_optimizer.py`、`effective_medium.py` 及其优化/拓扑算法归 TPC；本仓库只接收 `curves.py`/`s2p.py` 的通用实现，并在 `cst_automation` 下维护单份实现。
- 原整仓 `pyproject.toml`、README、通用+CST+TPC 混合 skills、CST MCP 旧模板建模工具和相应拓扑专属 MCP 测试不整包复制；以独立发行配置、四个聚焦 skill 和通用 MCP 工具替代。
- 源 `THIRD_PARTY_NOTICES.md` 指向未迁移的第三方参考手册和 vendored 文档；这些参考件未复制，故不带入过期声明。根 MIT `LICENSE` 已保留。
- 源仓库其他用户修改仍留在原目录；当前目录在收到严格只读要求后未写入。源 Git `status` 无法工作，因此快照仅能保证覆盖本次迁移涉及的 111 个源码/测试/文档输入，不能据此声明源工作区干净。

## 兼容性约定

- 继续发行 `cst_solver`、`tpc_service`、`cst_mcp` 导入名；MCP 从 nested `src` 布局移到仓库根目录。
- 原 `tpc_toolkit.curves` 与 `s2p` 的通用算法实现进入 `cst_automation.curves`/`s2p`；TPC 仓库负责维护旧路径延迟 shim。
- CST 后端仅解决现有工程；领域建模与 study 通过 `RunService.register_handler` 显式接入。完整协议见 `PUBLIC_API.md`。
