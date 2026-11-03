"""Offline, auditable SVG schematic preview from the exact circuit specification."""
import csv
import html
import json
from pathlib import Path

from .circuit_schema import validate_circuit_spec, spec_digest


def preview_circuit(spec, output_dir):
    data = validate_circuit_spec(spec)
    digest = spec_digest(data)
    folder = Path(output_dir)
    folder.mkdir(parents=True, exist_ok=True)
    objects = data["blocks"] + data["external_ports"] + [{"name": link["block_name"], "properties": {"EM source": link["source"]}} for link in data["em_links"]]
    positions = {obj["name"]: obj.get("position", [49000 + i * 600, 50000]) for i, obj in enumerate(objects)}
    xs = [p[0] for p in positions.values()] or [0]
    ys = [p[1] for p in positions.values()] or [0]
    def point(name):
        x, y = positions[name]
        return 100 + (x - min(xs)) / max(600, max(xs) - min(xs)) * 850, 110 + (y - min(ys)) / max(600, max(ys) - min(ys)) * 350
    esc = lambda text: html.escape(str(text))
    svg = ['<svg xmlns="http://www.w3.org/2000/svg" width="1120" height="650" viewBox="0 0 1120 650">',
           '<rect width="1120" height="650" fill="#fafaf7"/>',
           '<text x="32" y="38" font-family="Arial" font-size="23">Circuit topology preview — offline, not CST readback</text>']
    rows = []
    for net in data["nets"]:
        ends = net["endpoints"]
        x0, y0 = point(ends[0]["component_name"])
        for endpoint in ends:
            x, y = point(endpoint["component_name"])
            svg.append(f'<path d="M{x0},{y0} L{x},{y}" fill="none" stroke="#597681" stroke-width="2"/>')
            rows.append([net["name"], endpoint["component_kind"], endpoint["component_name"], endpoint["pin_name"]])
    for obj in objects:
        x, y = point(obj["name"])
        svg.append(f'<rect x="{x-65}" y="{y-24}" width="130" height="48" rx="3" fill="white" stroke="#263a45"/>')
        svg.append(f'<text x="{x}" y="{y+5}" text-anchor="middle" font-family="Arial" font-size="16">{esc(obj["name"])}</text>')
        label = "; ".join(f'{key}={value} {obj.get("property_units", {}).get(key, "")}' for key, value in obj.get("properties", {}).items())
        svg.append(f'<text x="{x}" y="{y+48}" text-anchor="middle" font-family="Arial" font-size="13">{esc(label)}</text>')
    svg.append(f'<text x="32" y="580" font-family="Arial" font-size="12">Topology only; pin names are authoritative in connections.csv. Layout is not physical geometry.</text>')
    svg.append(f'<text x="32" y="610" font-family="monospace" font-size="11">SHA-256: {digest}</text></svg>')
    (folder / "circuit.svg").write_text("\n".join(svg), encoding="utf-8")
    with (folder / "connections.csv").open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.writer(handle)
        writer.writerow(["net", "component_kind", "component_name", "pin_name"])
        writer.writerows(rows)
    (folder / "circuit.json").write_text(json.dumps({"spec": data, "spec_digest": digest, "evidence": "offline_preview"}, ensure_ascii=False, indent=2), encoding="utf-8")
    return {"spec_digest": digest, "evidence": "offline_preview", "artifacts": [str((folder / n).resolve()) for n in ("circuit.svg", "connections.csv", "circuit.json")]}
