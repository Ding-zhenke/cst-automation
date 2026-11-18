"""Bundle repository skills unchanged, with their documentation, as a Codex plugin.

Uses only the standard library and never imports or starts CST.
"""
from pathlib import Path
import json
import os
import re
import tempfile
from urllib.parse import unquote, urlsplit
from zipfile import ZIP_DEFLATED, ZipFile


def local_links(markdown):
    """Yield relative inline Markdown links outside fenced examples."""
    for line in re.sub(r"^```[^\n]*\n.*?^```[^\n]*$", "", markdown, flags=re.M | re.S).splitlines():
        for target in re.findall(r"\]\(([^\s)]+)\)", line):
            parsed = urlsplit(target)
            if not parsed.scheme and not parsed.netloc:
                yield unquote(parsed.path), unquote(parsed.fragment)


def release_files(root, skill_dirs):
    files = {root / "skills/README.md", root / "docs/guides/codex-plugin.md"}
    for directory in skill_dirs:
        files.add(directory / "SKILL.md")
        for pattern in ("LICENSE", "scripts/*.py", "scripts/*.ps1",
                        "assets/*.mplstyle", "agents/openai.yaml"):
            files.update(path for path in directory.glob(pattern) if path.is_file())

    pending = sorted(path for path in files if path.suffix == ".md")
    while pending:
        source = pending.pop()
        for name, _ in local_links(source.read_text(encoding="utf-8")):
            if not name:
                continue
            target = (source.parent / name).resolve()
            if target in files:
                continue
            relative = target.relative_to(root)
            skill_reference = target.parent.name == "references" and target.parent.parent in skill_dirs
            guide = relative.parts[:2] in (("docs", "guides"), ("docs", "packages"))
            if target.suffix != ".md" or not (
                skill_reference or guide or relative == Path("docs/PUBLIC_API.md")
            ):
                raise ValueError(f"{source.relative_to(root)} links outside plugin inputs: {name}")
            if not target.is_file():
                raise ValueError(f"Missing plugin reference: {source.relative_to(root)} -> {name}")
            files.add(target)
            pending.append(target)
    return sorted(files)


def build_plugin(root: Path) -> Path:
    root = root.resolve()
    template = root / "plugins" / "cst-automation" / ".codex-plugin" / "plugin.json"
    manifest = json.loads(template.read_text(encoding="utf-8"))
    if manifest["name"] != "cst-automation" or manifest["skills"] != "./skills/":
        raise ValueError("Unexpected plugin identity or skills directory")
    # Root identity wins over the compatibility overlay in current clients.
    # Derive both from one source so an upgrade replaces stale root metadata.
    portable = {
        "$schema": "https://agent-plugins.org/schemas/1.0.0/plugin.schema.json",
        **{key: manifest[key] for key in ("name", "version", "description", "author",
                                          "repository", "license", "keywords") if key in manifest},
        "extensions": {"com.openai": {"interface": manifest["interface"]}},
    }
    portable_json = json.dumps(portable, ensure_ascii=False, indent=2) + "\n"
    skill_dirs = sorted(p.parent for p in (root / "skills").glob("*/SKILL.md"))
    if not skill_dirs:
        raise ValueError("No repository skills found")

    # Explicit inputs keep environments, projects, credentials, and work/ out.
    entries = [(template, ".codex-plugin/plugin.json"), (root / "LICENSE", "LICENSE"),
               (template.parents[1] / "README.md", "README.md")]
    for source in release_files(root, skill_dirs):
        source.resolve().relative_to(root)
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
            bundle.writestr("plugin.json", portable_json)
            for source, target in entries:
                bundle.write(source, target)
        with ZipFile(marketplace_archive, "w", compression=ZIP_DEFLATED) as bundle:
            bundle.writestr(".agents/plugins/marketplace.json", json.dumps(marketplace, indent=2))
            bundle.writestr("plugins/cst-automation/plugin.json", portable_json)
            for source, target in entries:
                bundle.write(source, "plugins/cst-automation/" + target)
        os.replace(archive, destination)
        os.replace(marketplace_archive, marketplace_destination)
    return destination


if __name__ == "__main__":
    print(build_plugin(Path(__file__).resolve().parents[1]))
