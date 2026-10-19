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
python -B -m pytest -o addopts='' -q
python -B -m build --wheel --sdist
```

The test suite must not require a local CST installation, a user-specific absolute path, or an external project checkout. Use stubs/fake backends for SDK and service behavior. Do not describe mocked geometry, result parsing, or solver outcomes as live CST evidence.

## API and evidence changes

- Keep `cst_solver`, `tpc_service`, and `cst_mcp` import names stable unless the public API contract is deliberately revised.
- Keep domain code outside this repository. Add extension points and document them in `docs/PUBLIC_API.md`.
- Keep repository skills under `.github/skills/`, link them from the README and `AGENTS.md`, and direct agents to read the index before selecting a skill. Do not rely on runtime-specific automatic discovery or installation under `.agents/skills`.
- Record source ownership in `docs/MIGRATION_MAP.md` and observed checks/boundaries in `docs/VALIDATION.md`.
- Do not add personal installation paths, CST project files, license-server details, credentials, or unreviewed simulation outputs.
- Keep geometry checks, CST readback, real solver execution, and device-performance claims as separate evidence levels.

## Release build

The GitHub Actions workflow runs offline tests, MCP protocol tests, and wheel/sdist builds on clean Windows runners. Review the artifact metadata and `docs/VALIDATION.md` before creating a release.
