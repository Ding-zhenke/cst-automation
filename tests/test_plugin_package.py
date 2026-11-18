"""Verify the distributable plugin without loading CST or changing source skills."""
import importlib.util
import json
from pathlib import Path
import re
import shutil
import unicodedata
from zipfile import ZipFile

import pytest


ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("build_plugin", ROOT / "scripts/build_plugin.py")
builder = importlib.util.module_from_spec(spec)
spec.loader.exec_module(builder)


def heading_ids(markdown):
    ids = set(re.findall(r'<a\s+(?:name|id)="([^"]+)"', markdown))
    fence = False
    for line in markdown.splitlines():
        if line.startswith("```"):
            fence = not fence
            continue
        heading = re.match(r"^#{1,6}\s+(.+?)\s*#*\s*$", line) if not fence else None
        if heading:
            text = heading.group(1).lower()
            slug = "".join(c for c in text if c in "-_ " or unicodedata.category(c)[0] in "LMN").replace(" ", "-")
            key = slug
            number = 0
            while key in ids:
                number += 1
                key = f"{slug}-{number}"
            ids.add(key)
    return ids


def assert_local_links(root, paths):
    headings = {}
    for path in paths:
        for target, fragment in builder.local_links(path.read_text(encoding="utf-8")):
            resolved = (path.parent / target).resolve() if target else path
            assert root.resolve() in resolved.parents and resolved.is_file(), (path, target)
            if fragment and resolved.suffix == ".md":
                if resolved not in headings:
                    headings[resolved] = heading_ids(resolved.read_text(encoding="utf-8"))
                assert fragment in headings[resolved], (path, target, fragment)


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
    (tmp_path / "docs/guides/unlinked.md").write_text("Private draft", encoding="utf-8")
    (tmp_path / "skills/cst-circuit/private.json").write_text("{}", encoding="utf-8")
    (tmp_path / "skills/cst-circuit/references/unlinked.md").write_text("Draft", encoding="utf-8")
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
        assert set(entries) == {p for p in before if p.endswith("/SKILL.md")}
        assert {"README.md", "skills/keysight-ads-simulation/LICENSE",
                "skills/keysight-ads-simulation/agents/openai.yaml",
                "skills/cst-figures/assets/research.mplstyle",
                "skills/cst-sessions/scripts/check_workflow.py",
                "skills/keysight-ads-simulation/scripts/invoke_hidden.ps1"} <= names
        assert not names.intersection({".env", "docs/guides/unlinked.md", "docs/VALIDATION.md",
                                       "skills/cst-circuit/private.json", "docs/MIGRATION_MAP.md",
                                       "skills/cst-circuit/references/unlinked.md"})
        assert not any(n.startswith(("docs/superpowers/", "docs/validation/")) for n in names)
        for name, content in before.items():
            if any(part in ("__pycache__", "tests") for part in Path(name).parts) or name.endswith((".pyc", "private.json", "unlinked.md")):
                assert name not in names
                continue
            assert bundle.read(name) == content
        extracted = tmp_path / "unpacked"
        extracted.mkdir()
        # Simulate upgrading an existing source whose portable identity is stale.
        (extracted / "plugin.json").write_text(json.dumps({"name": "cst-automation", "version": "0.0.0"}), encoding="utf-8")
        bundle.extractall(extracted)
        assert json.loads((extracted / "plugin.json").read_text(encoding="utf-8"))["version"] == manifest["version"]
        assert_local_links(extracted, sorted(extracted.rglob("*.md")))
        assert all(n in ("LICENSE", "README.md", "plugin.json", ".codex-plugin/plugin.json")
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


def test_link_to_repository_private_file_refuses_build(tmp_path):
    skill = tmp_path / "skills/demo"
    skill.mkdir(parents=True)
    (skill / "SKILL.md").write_text("[private](../../work/secrets.md)", encoding="utf-8")
    (tmp_path / "skills/README.md").touch()
    guide = tmp_path / "docs/guides/codex-plugin.md"
    guide.parent.mkdir(parents=True)
    guide.touch()
    with pytest.raises(ValueError, match="outside plugin inputs"):
        builder.release_files(tmp_path, [skill])
