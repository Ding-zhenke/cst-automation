# Contributing

## Local setup

Use Python 3.11 for the complete suite, including MCP protocol tests. Python 3.9 is supported for the core package and offline service/data APIs; MCP protocol tests require the optional MCP SDK extra, which supports Python 3.10+.

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e ".[dev,mcp]"
```

## Verify changes

Run the offline suite and build both release artifacts:

```powershell
$env:PYTHONDONTWRITEBYTECODE = '1'
python -B -m pytest -o addopts='' -m "not gui" -q
python -B -m build --wheel --sdist
```

常规离线套件排除 `gui` 标记的真实桌面测试。需要交互式 Windows 会话的 UI Automation 测试应显式运行：`python -B -m pytest -o addopts='' -m gui -q cst_solver/tests/test_dialog_windows.py`。常规测试不得要求本机 CST、用户专属绝对路径或外部项目 checkout；使用 stub/fake backend 验证 SDK 与服务行为。不得把模拟几何、结果解析或求解状态描述为真实 CST 证据。

## API and evidence changes

- Keep `cst_solver`, `tpc_service`, and `cst_mcp` import names stable unless the public API contract is deliberately revised.
- Keep domain code outside this repository. Add extension points and document them in `docs/PUBLIC_API.md`.
- Keep repository skills under `skills/`, link them from the README and `AGENTS.md`, and direct agents to read the index before selecting a skill. The repository-root `skills/` directory is the single canonical location; route readers through `AGENTS.md`.
- Record source ownership in `docs/MIGRATION_MAP.md` and observed checks/boundaries in `docs/VALIDATION.md`.
- Do not add personal installation paths, CST project files, license-server details, credentials, or unreviewed simulation outputs.
- Keep geometry checks, CST readback, real solver execution, and device-performance claims as separate evidence levels.

## Release build

The GitHub Actions workflow runs offline tests, MCP protocol tests, and wheel/sdist builds on clean Windows runners. Review the artifact metadata and `docs/VALIDATION.md` before creating a release.
