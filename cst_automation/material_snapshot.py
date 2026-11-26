"""Read-only access to material values stored in a saved CST model cache.

This module does not connect to CST. The result describes the saved
``ModelCache/Model.mif`` snapshot and is not a live material readback.
"""
from __future__ import annotations

import hashlib
import math
import re
from pathlib import Path
from typing import Any


class MaterialSnapshotError(ValueError):
    """The saved project cache is missing or cannot prove the requested data."""


_MATERIAL_START = re.compile(r'^\[MATERIAL:\s*(.*?)\s*\]$', re.IGNORECASE)
_PROPERTY = re.compile(r'^\s*\.([A-Za-z0-9_]+)\s+(.+?)\s*$')
_END_MATERIAL = '[ENDMATERIAL]'
_REQUIRED_NUMERIC_FIELDS = {
    'larmor_rad_s': 'DispCoeff1Mu',
    'gyro_rad_s': 'DispCoeff2Mu',
    'damping': 'DispCoeff3Mu',
}
_BIAS_FIELDS = ('DispCoeff4MuX', 'DispCoeff4MuY', 'DispCoeff4MuZ')
_TARGET_FIELDS = {
    'type', 'dispmodelmu', 'usesisystem',
    *(field.lower() for field in _REQUIRED_NUMERIC_FIELDS.values()),
    *(field.lower() for field in _BIAS_FIELDS),
}


def _project_cache_path(project_path: str | Path) -> Path:
    try:
        project = Path(project_path).expanduser().resolve(strict=True)
    except (OSError, RuntimeError, TypeError, ValueError) as exc:
        raise MaterialSnapshotError('project_path must name an existing saved .cst file') from exc
    if not project.is_file() or project.suffix.lower() != '.cst':
        raise MaterialSnapshotError('project_path must name an existing saved .cst file')
    cache = project.with_suffix('') / 'ModelCache' / 'Model.mif'
    if not cache.is_file():
        raise MaterialSnapshotError(f'saved ModelCache/Model.mif is missing: {cache}')
    try:
        cache = cache.resolve(strict=True)
    except (OSError, RuntimeError) as exc:
        raise MaterialSnapshotError('saved ModelCache/Model.mif cannot be resolved') from exc
    return cache


def _material_blocks(text: str) -> list[tuple[str, list[str]]]:
    blocks: list[tuple[str, list[str]]] = []
    current_name: str | None = None
    current_lines: list[str] = []

    for line_number, line in enumerate(text.splitlines(), start=1):
        stripped = line.strip()
        upper = stripped.upper()
        start = _MATERIAL_START.fullmatch(stripped)
        if start:
            if current_name is not None:
                raise MaterialSnapshotError(
                    f'nested MATERIAL section at line {line_number}')
            name = start.group(1).strip()
            if not name:
                raise MaterialSnapshotError(f'empty MATERIAL name at line {line_number}')
            current_name, current_lines = name, []
            continue
        if upper.startswith('[MATERIAL:'):
            raise MaterialSnapshotError(f'malformed MATERIAL section at line {line_number}')
        if upper == _END_MATERIAL:
            if current_name is None:
                raise MaterialSnapshotError(f'ENDMATERIAL without MATERIAL at line {line_number}')
            blocks.append((current_name, current_lines))
            current_name, current_lines = None, []
            continue
        if upper.startswith('[ENDMATERIAL'):
            raise MaterialSnapshotError(f'malformed ENDMATERIAL section at line {line_number}')
        if current_name is not None:
            current_lines.append(line)

    if current_name is not None:
        raise MaterialSnapshotError(f'unterminated MATERIAL section: {current_name!r}')
    return blocks


def _properties(lines: list[str], material_name: str) -> dict[str, str]:
    properties: dict[str, str] = {}
    for line in lines:
        match = _PROPERTY.fullmatch(line)
        if not match:
            continue
        key, value = match.groups()
        normalized_key = key.lower()
        if normalized_key not in _TARGET_FIELDS:
            continue
        if normalized_key in properties:
            raise MaterialSnapshotError(
                f'duplicate {key} field in MATERIAL {material_name!r}')
        properties[normalized_key] = value
    return properties


def _quoted_value(properties: dict[str, str], key: str, material_name: str) -> str:
    value = properties.get(key.lower())
    if value is None or len(value) < 2 or value[0] != '"' or value[-1] != '"':
        raise MaterialSnapshotError(
            f'missing or invalid {key} field in MATERIAL {material_name!r}')
    return value[1:-1]


def _number(properties: dict[str, str], key: str, material_name: str) -> float:
    raw = _quoted_value(properties, key, material_name)
    try:
        value = float(raw)
    except ValueError as exc:
        raise MaterialSnapshotError(
            f'{key} in MATERIAL {material_name!r} is not a saved numeric value') from exc
    if not math.isfinite(value):
        raise MaterialSnapshotError(
            f'{key} in MATERIAL {material_name!r} must be finite')
    return value


def read_gyrotropic_material(project_path: str | Path,
                             material_name: str) -> dict[str, Any]:
    """Read exact SI magnetic Gyrotropic fields from a saved CST model cache.

    ``project_path`` is the saved ``.cst`` file. CST stores its companion cache
    at ``<project stem>/ModelCache/Model.mif``. Values are extracted only from
    one exact ``[MATERIAL: name]`` block in that file; model history and
    parameter tables are never used as substitutes.

    The returned ``saved_model_cache`` evidence applies to the saved cache
    snapshot identified by ``source_path`` and ``sha256``. It does not claim
    the live model is current or has been read back from CST.
    """
    if not isinstance(material_name, str) or not material_name or material_name != material_name.strip():
        raise MaterialSnapshotError('material_name must be a non-empty exact material name')

    cache_path = _project_cache_path(project_path)
    try:
        payload = cache_path.read_bytes()
        text = payload.decode('utf-8-sig')
    except (OSError, UnicodeDecodeError) as exc:
        raise MaterialSnapshotError(f'saved material cache cannot be read: {cache_path}') from exc

    matches = [(name, lines) for name, lines in _material_blocks(text)
               if name == material_name]
    if not matches:
        raise MaterialSnapshotError(f'MATERIAL {material_name!r} is missing from saved cache')
    if len(matches) != 1:
        raise MaterialSnapshotError(f'MATERIAL {material_name!r} is ambiguous in saved cache')

    _, material_lines = matches[0]
    properties = _properties(material_lines, material_name)
    material_type = _quoted_value(properties, 'Type', material_name)
    dispersion = _quoted_value(properties, 'DispModelMu', material_name)
    use_si = _quoted_value(properties, 'UseSISystem', material_name)
    if material_type != 'Normal' or dispersion != 'Gyrotropic' or use_si.lower() != 'true':
        raise MaterialSnapshotError(
            f'MATERIAL {material_name!r} is not a Normal SI magnetic Gyrotropic material')

    values = {name: _number(properties, field, material_name)
              for name, field in _REQUIRED_NUMERIC_FIELDS.items()}
    if values['larmor_rad_s'] < 0 or values['gyro_rad_s'] < 0 or values['damping'] < 0:
        raise MaterialSnapshotError(
            f'MATERIAL {material_name!r} has negative Gyrotropic parameters')

    bias = tuple(_number(properties, field, material_name) for field in _BIAS_FIELDS)
    if not math.isclose(math.hypot(*bias), 1.0, rel_tol=1e-9, abs_tol=1e-12):
        raise MaterialSnapshotError(
            f'MATERIAL {material_name!r} bias direction is not a unit vector')

    digest = hashlib.sha256(payload).hexdigest()
    return {
        'material_name': material_name,
        **values,
        'bias_direction': bias,
        'source_path': str(cache_path),
        'source_summary': (
            f'Saved ModelCache/Model.mif MATERIAL block {material_name!r}; '
            'offline saved-snapshot evidence, not a live CST readback.'),
        'evidence_type': 'saved_model_cache',
        'sha256': digest,
    }
