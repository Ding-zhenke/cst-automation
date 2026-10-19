"""Dependency inventory and offline staging; CST relocation needs live readback."""
import hashlib
import json
from pathlib import Path
import re
import shutil

from .adapter import CircuitError


def file_digest(path):
    result = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            result.update(chunk)
    return result.hexdigest()


def dependency_manifest(project_path, snapshot):
    project = Path(project_path).resolve()
    files, unknown, seen = [], [], set()

    def walk(path, stack=()):
        path = path.resolve()
        key = str(path).casefold()
        if key in stack:
            unknown.append({"path": str(path), "reason": "dependency cycle"})
            return
        if key in seen:
            return
        seen.add(key)
        exists = path.is_file()
        files.append({"path": str(path), "exists": exists, "sha256": file_digest(path) if exists else None})
        if not exists:
            return
        suffix = path.suffix.lower()
        if suffix in (".cir", ".lib", ".sp", ".spice", ".mod"):
            try:
                text = path.read_text(encoding="utf-8-sig")
                for line in text.splitlines():
                    if re.match(r"\s*\.(include|inc|lib)\b", line, re.I):
                        match = re.fullmatch(r'\s*\.(?:include|inc)\s+(?:"([^"]+)"|\x27([^\x27]+)\x27|(\S+))\s*', line, re.I)
                        if not match:
                            unknown.append({"path": str(path), "reason": "Unsupported SPICE include/lib directive", "line": line})
                        else:
                            target = next(g for g in match.groups() if g is not None)
                            walk(path.parent / target, stack + (key,))
            except (OSError, UnicodeError) as exc:
                unknown.append({"path": str(path), "reason": str(exc)})
        elif suffix in (".cst", ".prj") and path != project:
            unknown.append({"path": str(path), "reason": "External CST dependency closure requires schematic readback"})
        elif path != project and not re.fullmatch(r"\.s\d+p", suffix):
            unknown.append({"path": str(path), "reason": "Unknown dependency format"})

    walk(project)
    for block in snapshot.get("blocks", []):
        if block.get("files") is None:
            unknown.append({"block": block["name"], "reason": "SDK file list unavailable"})
        else:
            for filename in block["files"]:
                if filename:
                    walk(project.parent / filename)
    return {"project": str(project), "files": files, "unknown": unknown,
            "complete": not unknown and all(f["exists"] for f in files), "evidence": "dependency_inventory"}


def bundle_project(project_path, manifest, destination):
    """Stage copies without patching a binary CST file or claiming portability."""
    source, target = Path(project_path).resolve(), Path(destination).resolve()
    if not manifest.get("complete"):
        raise CircuitError("circuit_dependency_missing", "Dependency closure incomplete", manifest=manifest)
    if target.exists():
        raise CircuitError("circuit_spec_invalid", "Bundle destination already exists; no overwrite")
    if source.parent == target or source.with_suffix("") == target or source.with_suffix("") in target.parents:
        raise CircuitError("circuit_spec_invalid", "Bundle destination overlaps source")
    target.mkdir(parents=True)
    copied = []
    try:
        shutil.copy2(source, target / source.name)
        companion = source.with_suffix("")
        if companion.is_dir():
            shutil.copytree(companion, target / companion.name)
        for entry in manifest["files"]:
            path = Path(entry["path"]).resolve()
            if path == source:
                continue
            if file_digest(path) != entry["sha256"]:
                raise CircuitError("circuit_dependency_missing", "Dependency changed since inventory", path=str(path))
            relative = Path("dependencies") / entry["sha256"][:12] / path.name
            dest = target / relative
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(path, dest)
            copied.append({"source": str(path), "staged": str(dest), "sha256": entry["sha256"]})
        report = {"project": str(target / source.name), "copies": copied, "portable_verified": False,
                  "relocation_required": copied or [{"reason": "Reopen copied project and verify its resolved links"}],
                  "evidence": "offline_staging_only", "source_manifest": manifest}
        output = target / "dependencies.json"
        output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        report["artifacts"] = [str(output), str(target / source.name)]
        return report
    except Exception as exc:
        # Keep reviewable partial staging; never delete/rewrite the original.
        raise CircuitError("circuit_build_partial", f"Bundle staging failed: {exc}", destination=str(target)) from exc
