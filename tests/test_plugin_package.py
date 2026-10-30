"""Verify the distributable plugin without loading CST or changing source skills."""
import importlib.util
import json
from pathlib import Path
import re
import shutil
from zipfile import ZipFile


ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("build_plugin", ROOT / "scripts/build_plugin.py")
builder = importlib.util.module_from_spec(spec)
spec.loader.exec_module(builder)


def test_plugin_is_self_contained_and_preserves_skills(tmp_path):
    for directory in ("skills", "docs", "plugins"):
        shutil.copytree(ROOT / directory, tmp_path / directory)
    shutil.copyfile(ROOT / "LICENSE", tmp_path / "LICENSE")
    # Unrelated local files must never enter a plugin release.
    (tmp_path / ".env").write_text("PRIVATE=example", encoding="utf-8")
    before = {p.relative_to(tmp_path).as_posix(): p.read_bytes()
              for p in (tmp_path / "skills").rglob("*") if p.is_file()}
    archive = builder.build_plugin(tmp_path)
    with ZipFile(archive) as bundle:
        names = set(bundle.namelist())
        manifest = json.loads(bundle.read(".codex-plugin/plugin.json"))
        assert manifest["skills"] == "./skills/"
        assert "mcpServers" not in manifest
        entries = sorted(n for n in names if n.startswith("skills/") and n.endswith("/SKILL.md"))
        assert {Path(n).parent.name for n in entries} == {
            "cst-modeling", "cst-simulation", "cst-results", "cst-diagnostics"}
        for name, content in before.items():
            if name == "skills/README.md":
                continue
            assert bundle.read(name) == content
        extracted = tmp_path / "unpacked"
        bundle.extractall(extracted)
        for entry in entries:
            text = (extracted / entry).read_text(encoding="utf-8")
            for target in re.findall(r"\]\(([^)]+)\)", text):
                resolved = ((extracted / entry).parent / target).resolve()
                assert extracted.resolve() in resolved.parents
                assert resolved.is_file(), (entry, target)
        assert all(n == "LICENSE" or n == ".codex-plugin/plugin.json"
                   or n.startswith(("skills/", "docs/")) for n in names)
    assert before == {p.relative_to(tmp_path).as_posix(): p.read_bytes()
                      for p in (tmp_path / "skills").rglob("*") if p.is_file()}
    with ZipFile(tmp_path / "dist/cst-automation-marketplace.zip") as marketplace:
        catalog = json.loads(marketplace.read(".agents/plugins/marketplace.json"))
        entry = catalog["plugins"][0]
        prefix = entry["source"]["path"].removeprefix("./") + "/"
        assert entry["name"] == "cst-automation"
        with ZipFile(archive) as plugin:
            for name in plugin.namelist():
                assert marketplace.read(prefix + name) == plugin.read(name)
    # A second build works without deleting or editing source directories.
    assert builder.build_plugin(tmp_path) == archive
