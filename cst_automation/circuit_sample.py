"""Exact-parameter offline microstrip preview. Does not create a CST project."""
import csv
import json
from pathlib import Path

from .circuit_schema import spec_digest


def microstrip_sample():
    return {"unit": "mm", "coordinate_system": "global Cartesian; propagation along X",
            "solids": {
                "substrate": {"bounds": [[-10, 10], [-5, 5], [0, 0.8]], "material": {"epsilon_r": 2.2, "loss_tangent": 0}},
                "ground": {"bounds": [[-10, 10], [-5, 5], [-0.035, 0]], "material": "PEC"},
                "strip": {"bounds": [[-10, 10], [-1.2, 1.2], [0.8, 0.835]], "material": "PEC"}},
            "ports": [{"id": i, "type": "discrete", "p1": [x, 0, 0], "p2": [x, 0, 0.8],
                       "reference": "ground", "signal": "strip", "reference_impedance_ohm": 50,
                       "endpoint_direction": "p1 ground -> p2 strip; confirm CST voltage/current convention by readback"}
                      for i, x in ((1, -9.5), (2, 9.5))],
            "port_separation_mm": 19, "end_stub_length_mm": 0.5,
            "air_bounds": [[-15, 15], [-10, 10], [-5.035, 10.835]],
            "boundaries": {axis: "open at explicit air-box face; no additional automatic space" for axis in ("xmin", "xmax", "ymin", "ymax", "zmin", "zmax")},
            "frequency_ghz": [0.1, 5], "mesh_cell_budget": 200000,
            "geometry_verified": False, "solver_run": False, "approval": "pending",
            "notes": ["50 ohm is a port reference, not an assertion of line matching", "Both endpoints lie on conductor surfaces; no modeled gap",
                      "Port centers are inset 0.5 mm; the physical 20 mm strip includes both end stubs",
                      "Air boundaries, mesh and actual port polarity remain to be verified in CST after approval"]}


def preview_microstrip(output_dir, *, raster=True):
    data = microstrip_sample()
    root = Path(output_dir)
    root.mkdir(parents=True, exist_ok=True)
    digest = spec_digest(data)
    (root / "geometry.json").write_text(json.dumps({"geometry": data, "sha256": digest, "evidence": "offline_exact_parameter_preview"}, ensure_ascii=False, indent=2), encoding="utf-8")
    with (root / "ports.csv").open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.writer(handle)
        writer.writerow(["id", "type", "p1_x_mm", "p1_y_mm", "p1_z_mm", "p2_x_mm", "p2_y_mm", "p2_z_mm", "reference", "Zref_Ohm"])
        for p in data["ports"]:
            writer.writerow([p["id"], p["type"], *p["p1"], *p["p2"], p["reference"], p["reference_impedance_ohm"]])
    # Exact orthographic views; no exploded geometry or exaggerated layer thickness.
    svg = ['<svg xmlns="http://www.w3.org/2000/svg" width="1200" height="650" viewBox="0 0 1200 650">',
           '<rect width="1200" height="650" fill="#f8fafb"/>',
           '<g font-family="Arial" fill="#223747"><text x="35" y="40" font-size="25">3D EM / Design Studio validation specimen — preview for approval</text>',
           '<text x="35" y="70" font-size="15">Exact coordinates in mm. No CST model created; no solver run.</text>',
           '<text x="65" y="115" font-size="19">Top view (X-Y)</text>']
    for name, color in (("substrate", "#dce9eb"), ("strip", "#d49a42")):
        b = data["solids"][name]["bounds"]
        svg.append(f'<rect x="{245+b[0][0]*16}" y="{245-b[1][1]*16}" width="{(b[0][1]-b[0][0])*16}" height="{(b[1][1]-b[1][0])*16}" fill="{color}" stroke="#405c68"/>')
    for p in data["ports"]:
        x = 245 + p["p1"][0] * 16
        svg.append(f'<circle cx="{x}" cy="245" r="5" fill="#b8333e"/><text x="{x-20}" y="285" font-size="16">P{p["id"]}</text>')
    svg += ['<text x="120" y="350" font-size="16">L=20 mm; W=10 mm; strip width=2.4 mm</text>',
            '<text x="120" y="378" font-size="16">Port separation=19 mm; end stubs=0.5 mm</text>',
            '<text x="600" y="115" font-size="19">Cross-section (Y-Z, local crop)</text>']
    for name, color in (("ground", "#6c7f8a"), ("substrate", "#dce9eb"), ("strip", "#d49a42")):
        b = data["solids"][name]["bounds"]
        ymin, ymax = max(-1.8, b[1][0]), min(1.8, b[1][1])
        svg.append(f'<rect x="{825+ymin*100}" y="{300-b[2][1]*100}" width="{(ymax-ymin)*100}" height="{(b[2][1]-b[2][0])*100}" fill="{color}" stroke="#405c68" stroke-width="0.5"/>')
    svg += ['<path d="M825,300 L825,220 M820,226 L825,220 L830,226" stroke="#b8333e" stroke-width="2" fill="none"/>',
            '<text x="600" y="350" font-size="16">Substrate h=0.8 mm; both PEC layers t=0.035 mm</text>',
            '<text x="600" y="378" font-size="16">Arrow: ground z=0 to strip z=0.8; no gap</text>',
            '<text x="35" y="440" font-size="16">P1: (-9.5,0,0) → (-9.5,0,0.8); P2: (9.5,0,0) → (9.5,0,0.8)</text>',
            '<text x="35" y="470" font-size="16">Air box: X [-15,15], Y [-10,10], Z [-5.035,10.835]; open boundaries</text>',
            '<text x="35" y="500" font-size="16">εr=2.2, lossless; PEC conductors; port Zref=50 Ω (line matching unverified)</text>',
            '<text x="35" y="530" font-size="16">Planned band 0.1–5 GHz; mesh budget ≤200,000 cells; construction requires approval</text>',
            f'<text x="35" y="600" font-size="12">SHA-256: {digest}</text></g></svg>']
    (root / "geometry.svg").write_text("\n".join(svg), encoding="utf-8")
    artifacts = [str((root / name).resolve()) for name in ("geometry.json", "geometry.svg", "ports.csv")]
    if raster:
        artifacts.append(_raster(data, root))
    return {"evidence": "offline_exact_parameter_preview", "sha256": digest, "artifacts": artifacts}


def _raster(data, root):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.patches import Rectangle
    from mpl_toolkits.mplot3d.art3d import Poly3DCollection
    fig = plt.figure(figsize=(15, 7.5), facecolor="#f8fafb")
    ax = fig.add_subplot(131, projection="3d", computed_zorder=False)
    ax.set_facecolor(fig.get_facecolor())
    colors = {"ground": "#617888", "substrate": "#bdd9df", "strip": "#d79536"}
    for layer, name in enumerate(("ground", "substrate", "strip"), 1):
        (x0, x1), (y0, y1), (z0, z1) = data["solids"][name]["bounds"]
        vertices = [(x0,y0,z0),(x1,y0,z0),(x1,y1,z0),(x0,y1,z0),(x0,y0,z1),(x1,y0,z1),(x1,y1,z1),(x0,y1,z1)]
        faces = [[vertices[i] for i in ids] for ids in ((0,1,2,3),(4,5,6,7),(0,1,5,4),(1,2,6,5),(2,3,7,6),(3,0,4,7))]
        ax.add_collection3d(Poly3DCollection(faces, facecolors=colors[name], edgecolors="#395262", linewidths=.3, alpha=.85 if name == "substrate" else 1, zorder=layer))
    for port in data["ports"]:
        x, y, z = port["p1"]
        ax.plot([x, x], [y, y], [z, .8], color="#bc3146", linewidth=3, zorder=10)
        ax.text(x, y, 1, f'P{port["id"]}', color="#bc3146", zorder=11)
    ax.set(xlim=(-11,11), ylim=(-6,6), zlim=(-.1,1), xlabel="X (mm)", ylabel="Y (mm)", zlabel="Z (mm)")
    ax.set_box_aspect((22,12,1.1))
    ax.set_zticks([])
    ax.set_zlabel("")
    ax.view_init(elev=24, azim=-65)
    ax.set_title("3D geometry / true layer proportions", fontsize=11, pad=22)
    top = fig.add_subplot(132)
    for name in ("substrate", "strip"):
        b = data["solids"][name]["bounds"]
        top.add_patch(Rectangle((b[0][0],b[1][0]),b[0][1]-b[0][0],b[1][1]-b[1][0],facecolor=colors[name],edgecolor="#395262"))
    for port in data["ports"]:
        top.plot(port["p1"][0], 0, "o", color="#bc3146")
        top.annotate(f'P{port["id"]}', (port["p1"][0],0), xytext=(port["p1"][0],-3), ha="center", arrowprops={"arrowstyle":"->", "color":"#bc3146"})
    top.set(xlim=(-11,11),ylim=(-6,6),xlabel="X (mm)",ylabel="Y (mm)",title="Top view / port planes 19 mm apart")
    top.set_aspect("equal")
    cross = fig.add_subplot(133)
    for name in ("ground", "substrate", "strip"):
        b = data["solids"][name]["bounds"]
        cross.add_patch(Rectangle((b[1][0],b[2][0]),b[1][1]-b[1][0],b[2][1]-b[2][0],facecolor=colors[name],edgecolor="#395262",linewidth=.5))
    cross.annotate("", (0,.8), (0,0), arrowprops={"arrowstyle":"->", "color":"#bc3146","lw":2})
    cross.set(xlim=(-1.8,1.8),ylim=(-.15,1.05),xlabel="Y (mm)",ylabel="Z (mm)",title="Cross-section crop / equal scale")
    cross.set_aspect("equal")
    fig.suptitle("EM / Design Studio specimen — exact geometry and discrete-port preview", fontsize=18, x=.5, y=.96)
    fig.text(.06,.18,"Substrate: 20 x 10 x 0.8 mm, epsilon_r=2.2, lossless. Strip: 20 x 2.4 x 0.035 mm. Ground: 20 x 10 x 0.035 mm. Both PEC.",fontsize=10)
    fig.text(.06,.135,"P1: (-9.5,0,0) -> (-9.5,0,0.8) mm; P2: (9.5,0,0) -> (9.5,0,0.8) mm. Ground-to-strip endpoints; 50 ohm reference.",fontsize=10)
    fig.text(.06,.09,"Air box: X +/-15, Y +/-10, Z [-5.035,10.835] mm; open boundaries. Band: 0.1–5 GHz. Mesh budget: 200,000 cells.",fontsize=10)
    fig.text(.06,.045,"REVIEW ONLY — no CST geometry created, no rebuild, no solver run; 50 ohm line matching is not asserted.",fontsize=11,color="#a0293e")
    fig.subplots_adjust(left=.05,right=.96,bottom=.28,top=.86,wspace=.4)
    path = root / "geometry.png"
    fig.savefig(path,dpi=180,facecolor=fig.get_facecolor())
    plt.close(fig)
    return str(path.resolve())
