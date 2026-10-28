"""Bundle repository skills unchanged, with their documentation, as a Codex plugin.

Uses only the standard library and never imports or starts CST.
"""
from pathlib import Path
import json
import os
import tempfile
from zipfile import ZIP_DEFLATED, ZipFile


def build_plugin(root: Path) -> Path:
    root = root.resolve()
    template = root / "plugins" / "cst-automation" / ".codex-plugin" / "plugin.json"
    manifest = json.loads(template.read_text(encoding="utf-8"))
    if manifest["name"] != "cst-automation" or manifest["skills"] != "./skills/":
        raise ValueError("Unexpected plugin identity or skills directory")
    skill_dirs = sorted(p.parent for p in (root / "skills").glob("*/SKILL.md"))
    if not skill_dirs:
        raise ValueError("No repository skills found")

    # Explicit inputs keep environments, projects, credentials, and work/ out.
    entries = [(template, ".codex-plugin/plugin.json"), (root / "LICENSE", "LICENSE")]
    for directory in [*skill_dirs, root / "docs"]:
        for source in sorted(directory.rglob("*")):
            if source.is_file() and "__pycache__" not in source.parts and source.suffix != ".pyc":
                entries.append((source, source.relative_to(root).as_posix()))

    output_dir = root / "dist"
    output_dir.mkdir(exist_ok=True)
    destination = output_dir / "cst-automation-plugin.zip"
    marketplace_destination = output_dir / "cst-automation-marketplace.zip"
    marketplace = {
        "name": "cst-automation-local",
        "interface": {"displayName": "CST Automation Local"},
        "plugins": [{
            "name": "cst-automation",
            "source": {"source": "local", "path": "./plugins/cst-automation"},
            "policy": {"installation": "AVAILABLE", "authentication": "ON_INSTALL"},
            "category": "Productivity",
        }],
    }
    # Write both complete archives before replacing either existing output.
    with tempfile.TemporaryDirectory(prefix="plugin-build-", dir=output_dir) as staging:
        archive = Path(staging) / destination.name
        marketplace_archive = Path(staging) / marketplace_destination.name
        with ZipFile(archive, "w", compression=ZIP_DEFLATED) as bundle:
            for source, target in entries:
                bundle.write(source, target)
        with ZipFile(marketplace_archive, "w", compression=ZIP_DEFLATED) as bundle:
            bundle.writestr(".agents/plugins/marketplace.json", json.dumps(marketplace, indent=2))
            for source, target in entries:
                bundle.write(source, "plugins/cst-automation/" + target)
        os.replace(archive, destination)
        os.replace(marketplace_archive, marketplace_destination)
    return destination


if __name__ == "__main__":
    print(build_plugin(Path(__file__).resolve().parents[1]))
