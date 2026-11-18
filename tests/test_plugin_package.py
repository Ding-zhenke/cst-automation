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


def test_first_native_call_guidance_at_each_skill_entry():
    """A skill can be selected directly, without first loading the sessions skill."""
    routes = {
        "cst-simulation": ("app.run()",),
        "cst-sessions": ("worker", "resume"),
        "cst-diagnostics": ("--probe",),
        "cst-results": ("cst.results",),
    }
    for skill, native_operation in routes.items():
        entry = ROOT / "skills" / skill / "SKILL.md"
        paragraphs = entry.read_text(encoding="utf-8").split("\n\n")
        guidance = next((p for p in paragraphs if all(word in p for word in native_operation)), "")
        assert 'sandbox_permissions="require_escalated"' in guidance, skill
        assert re.search(r"\bfirst\b|首次|首条", guidance, re.IGNORECASE), skill

    # Keep ordinary installation discovery and exported data usable offline.
    for skill, example in (("cst-diagnostics", "doctor --json`"), ("cst-results", "CSV")):
        entry = ROOT / "skills" / skill / "SKILL.md"
        prose = " ".join(entry.read_text(encoding="utf-8").split())
        sentences = re.split(r"(?<=[.!?。])\s+", prose)
        assert any(example in s and "sandbox" in s.lower() for s in sentences), skill


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
        portable = json.loads(bundle.read("plugin.json"))
        assert portable["$schema"] == "https://agent-plugins.org/schemas/1.0.0/plugin.schema.json"
        for key in ("name", "version", "description", "author", "repository", "license"):
            assert portable[key] == manifest[key]
        assert portable["extensions"]["com.openai"]["interface"] == manifest["interface"]
        assert manifest["skills"] == "./skills/"
        assert bundle.read('skills/README.md') == before['skills/README.md']
        assert "mcpServers" not in manifest
        entries = sorted(n for n in names if n.startswith("skills/") and n.endswith("/SKILL.md"))
        assert {Path(n).parent.name for n in entries} == {
            "cst-circuit", "cst-device-characterization", "cst-diagnostics",
            "cst-diode-loading", "cst-figures", "cst-mesh-frequency", "cst-modeling",
            "cst-parameter-study", "cst-results", "cst-sessions", "cst-simulation",
            "cst-in-situ-validation", "keysight-ads-simulation", "diode-isolator-design-workflow"}
        for name, content in before.items():
            if '__pycache__' in Path(name).parts or name.endswith('.pyc'):
                assert name not in names
                continue
            assert bundle.read(name) == content
        extracted = tmp_path / "unpacked"
        extracted.mkdir()
        # Simulate upgrading an existing source whose portable identity is stale.
        (extracted / "plugin.json").write_text(json.dumps({"name": "cst-automation", "version": "0.0.0"}), encoding="utf-8")
        bundle.extractall(extracted)
        assert json.loads((extracted / "plugin.json").read_text(encoding="utf-8"))["version"] == manifest["version"]
        for entry in [*entries, 'skills/README.md',
                      'skills/cst-sessions/references/workflow-checkpoint.md']:
            text = (extracted / entry).read_text(encoding="utf-8")
            for target in re.findall(r"\]\(([^)]+)\)", text):
                # Markdown heading fragments are not part of the file path.
                resolved = ((extracted / entry).parent / target.split("#", 1)[0]).resolve()
                assert extracted.resolve() in resolved.parents
                assert resolved.is_file(), (entry, target)
        assert all(n in ("LICENSE", "plugin.json", ".codex-plugin/plugin.json")
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
