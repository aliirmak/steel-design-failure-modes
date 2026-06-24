"""
Generate a CalculiX / PrePoMax starter model for bearing and tearout
around a bolt hole in an A992 steel plate/web.

This is a robust "bearing + tearout proxy" model:
- 2D plane-stress plate
- one bolt hole near a free edge
- right edge fixed
- left-side arc of the hole is displaced leftward to mimic bolt bearing
- plastic strain localization indicates likely tearout path

This model intentionally avoids contact for the first version. Full bolt-hole
contact is possible later, but contact adds convergence headaches. This version
is better for a clean teaching/demo run.

Units:
- Length: inch
- Stress: ksi
- Force: kip
- Time: arbitrary

Dependencies:
    py -m pip install gmsh

Run:
    py make_bearing_tearout_demo.py
Then run CalculiX:
    ccx bearing_tearout_demo_ccx

Or import bearing_tearout_demo_ccx.inp into PrePoMax and run/open results there.
"""

from __future__ import annotations

from pathlib import Path
from dataclasses import dataclass
import math
import sys


@dataclass
class ModelParams:
    # Geometry, inches
    # Plate represents a web/plate strip with a bolt hole near the left edge.
    length: float = 8.0
    height: float = 4.0
    thickness: float = 0.375

    # Hole geometry, inches
    hole_diameter: float = 13.0 / 16.0   # standard hole for 3/4 in bolt
    hole_center_x: float = 1.25          # edge distance from left edge to hole center
    hole_center_y: float = 0.0

    # Bearing arc: the part of the hole where the bolt pushes on the plate.
    # 180 degrees is the left side of the circular hole.
    bearing_arc_center_angle_deg: float = 180.0
    bearing_arc_half_width_deg: float = 50.0

    # Mesh sizes, inches
    mesh_global: float = 0.22
    mesh_near_hole: float = 0.035
    mesh_left_ligament: float = 0.050

    # Loading
    # Negative x displacement on the left side of the hole, mimicking the bolt
    # pulling toward the free edge.
    bolt_arc_displacement_x: float = -0.18

    # Material, ksi
    E: float = 29000.0
    nu: float = 0.30

    # Idealized A992 plastic curve: yield stress ksi, plastic strain
    # Replace with calibrated true stress / true plastic strain data if needed.
    plastic_curve: tuple[tuple[float, float], ...] = (
        (50.0, 0.000),
        (55.0, 0.010),
        (60.0, 0.050),
        (65.0, 0.120),
        (70.0, 0.180),
    )

    # Visualization threshold only. Not a fracture model.
    assumed_tearout_peeq: float = 0.15


def chunked_int_list(values: list[int], per_line: int = 16) -> str:
    lines = []
    for i in range(0, len(values), per_line):
        lines.append(", ".join(str(v) for v in values[i:i + per_line]))
    return "\n".join(lines) + "\n"


def angle_distance_deg(a: float, b: float) -> float:
    """Smallest absolute distance between two angles in degrees."""
    return abs((a - b + 180.0) % 360.0 - 180.0)


def read_nodes_and_elements_from_inp(inp_path: Path):
    nodes: dict[int, tuple[float, float, float]] = {}
    element_ids: list[int] = []

    mode = None
    with inp_path.open("r", encoding="utf-8", errors="ignore") as f:
        for raw in f:
            line = raw.strip()
            if not line or line.startswith("**"):
                continue

            if line.startswith("*"):
                lower = line.lower()
                if lower.startswith("*node"):
                    mode = "node"
                elif lower.startswith("*element"):
                    mode = "element"
                else:
                    mode = None
                continue

            if mode == "node":
                parts = [p.strip() for p in line.split(",") if p.strip()]
                if len(parts) >= 3:
                    nid = int(parts[0])
                    x = float(parts[1])
                    y = float(parts[2])
                    z = float(parts[3]) if len(parts) >= 4 else 0.0
                    nodes[nid] = (x, y, z)

            elif mode == "element":
                parts = [p.strip() for p in line.split(",") if p.strip()]
                if len(parts) >= 4:
                    eid = int(parts[0])
                    element_ids.append(eid)

    if not nodes:
        raise RuntimeError("No nodes were found in the Gmsh .inp file.")
    if not element_ids:
        raise RuntimeError("No elements were found in the Gmsh .inp file.")

    return nodes, element_ids


def make_gmsh_mesh(params: ModelParams, out_mesh_inp: Path, out_brep: Path | None = None):
    try:
        import gmsh
    except ImportError as exc:
        raise SystemExit(
            "The gmsh Python module is not installed.\n"
            "Install it with:\n"
            "    py -m pip install gmsh\n"
            "or:\n"
            "    python -m pip install gmsh\n"
        ) from exc

    gmsh.initialize(sys.argv)
    gmsh.model.add("bearing_tearout_demo")

    L = params.length
    H = params.height
    hx = params.hole_center_x
    hy = params.hole_center_y
    r = params.hole_diameter / 2.0

    # Rectangle centered vertically about y = 0
    rect = gmsh.model.occ.addRectangle(0.0, -H / 2.0, 0.0, L, H)
    disk = gmsh.model.occ.addDisk(hx, hy, 0.0, r, r)

    # Cut hole from plate
    cut_result, _ = gmsh.model.occ.cut(
        [(2, rect)],
        [(2, disk)],
        removeObject=True,
        removeTool=True,
    )
    gmsh.model.occ.synchronize()

    surfaces = [tag for dim, tag in cut_result if dim == 2]
    if not surfaces:
        raise RuntimeError("No plate surface was created after cutting the hole.")

    gmsh.model.addPhysicalGroup(2, surfaces, 1)
    gmsh.model.setPhysicalName(2, 1, "PLATE")

    # Identify boundary curves for refinement.
    boundary = gmsh.model.getBoundary([(2, s) for s in surfaces], oriented=False, recursive=False)

    hole_curves = []
    left_edge_curves = []

    tol = 1.0e-6
    for dim, tag in boundary:
        if dim != 1:
            continue
        xmin, ymin, zmin, xmax, ymax, zmax = gmsh.model.getBoundingBox(dim, tag)
        cx = 0.5 * (xmin + xmax)
        cy = 0.5 * (ymin + ymax)

        # Hole boundary curve is inside the plate and close to the hole center.
        if (xmin > tol and xmax < L - tol and ymin > -H / 2.0 + tol and ymax < H / 2.0 - tol):
            if math.hypot(cx - hx, cy - hy) < 1.1 * r:
                hole_curves.append(tag)

        # Left free edge where tearout would reach.
        if abs(xmin - 0.0) < tol and abs(xmax - 0.0) < tol:
            left_edge_curves.append(tag)

    gmsh.option.setNumber("Mesh.MeshSizeMin", params.mesh_near_hole)
    gmsh.option.setNumber("Mesh.MeshSizeMax", params.mesh_global)
    gmsh.option.setNumber("Mesh.Algorithm", 6)  # Frontal-Delaunay for 2D
    gmsh.option.setNumber("Mesh.ElementOrder", 1)
    gmsh.option.setNumber("Mesh.SaveGroupsOfNodes", 1)
    gmsh.option.setNumber("Mesh.SaveAll", 0)

    fields = []

    if hole_curves:
        field_dist = gmsh.model.mesh.field.add("Distance")
        gmsh.model.mesh.field.setNumbers(field_dist, "CurvesList", hole_curves)
        gmsh.model.mesh.field.setNumber(field_dist, "Sampling", 200)

        field_th = gmsh.model.mesh.field.add("Threshold")
        gmsh.model.mesh.field.setNumber(field_th, "InField", field_dist)
        gmsh.model.mesh.field.setNumber(field_th, "SizeMin", params.mesh_near_hole)
        gmsh.model.mesh.field.setNumber(field_th, "SizeMax", params.mesh_global)
        gmsh.model.mesh.field.setNumber(field_th, "DistMin", params.hole_diameter * 0.20)
        gmsh.model.mesh.field.setNumber(field_th, "DistMax", params.hole_diameter * 2.00)
        fields.append(field_th)

    if left_edge_curves:
        field_dist2 = gmsh.model.mesh.field.add("Distance")
        gmsh.model.mesh.field.setNumbers(field_dist2, "CurvesList", left_edge_curves)
        gmsh.model.mesh.field.setNumber(field_dist2, "Sampling", 100)

        field_th2 = gmsh.model.mesh.field.add("Threshold")
        gmsh.model.mesh.field.setNumber(field_th2, "InField", field_dist2)
        gmsh.model.mesh.field.setNumber(field_th2, "SizeMin", params.mesh_left_ligament)
        gmsh.model.mesh.field.setNumber(field_th2, "SizeMax", params.mesh_global)
        gmsh.model.mesh.field.setNumber(field_th2, "DistMin", 0.20)
        gmsh.model.mesh.field.setNumber(field_th2, "DistMax", 1.50)
        fields.append(field_th2)

    if len(fields) == 1:
        gmsh.model.mesh.field.setAsBackgroundMesh(fields[0])
    elif len(fields) > 1:
        min_field = gmsh.model.mesh.field.add("Min")
        gmsh.model.mesh.field.setNumbers(min_field, "FieldsList", fields)
        gmsh.model.mesh.field.setAsBackgroundMesh(min_field)

    gmsh.model.mesh.generate(2)

    gmsh.write(str(out_mesh_inp))

    if out_brep is not None:
        gmsh.write(str(out_brep))

    gmsh.finalize()


def build_calculix_deck(params: ModelParams, mesh_inp: Path, out_ccx_inp: Path):
    nodes, element_ids = read_nodes_and_elements_from_inp(mesh_inp)

    L = params.length
    H = params.height
    hx = params.hole_center_x
    hy = params.hole_center_y
    r = params.hole_diameter / 2.0

    coord_tol = max(1.0e-5, params.mesh_near_hole * 0.10)
    hole_tol = max(0.01, params.mesh_near_hole * 0.70)

    fixed_nodes = sorted(nid for nid, (x, y, z) in nodes.items() if abs(x - L) <= coord_tol)

    hole_boundary_nodes = []
    bearing_arc_nodes = []
    top_ligament_nodes = []
    bottom_ligament_nodes = []

    for nid, (x, y, z) in nodes.items():
        dist = math.hypot(x - hx, y - hy)
        if abs(dist - r) <= hole_tol:
            hole_boundary_nodes.append(nid)
            theta = math.degrees(math.atan2(y - hy, x - hx)) % 360.0
            if angle_distance_deg(theta, params.bearing_arc_center_angle_deg) <= params.bearing_arc_half_width_deg:
                bearing_arc_nodes.append(nid)

        # Useful node sets for inspecting tearout ligaments.
        if x < hx and abs(y - (hy + r)) < params.mesh_near_hole * 1.5:
            top_ligament_nodes.append(nid)
        if x < hx and abs(y - (hy - r)) < params.mesh_near_hole * 1.5:
            bottom_ligament_nodes.append(nid)

    fixed_nodes = sorted(set(fixed_nodes))
    hole_boundary_nodes = sorted(set(hole_boundary_nodes))
    bearing_arc_nodes = sorted(set(bearing_arc_nodes))
    top_ligament_nodes = sorted(set(top_ligament_nodes))
    bottom_ligament_nodes = sorted(set(bottom_ligament_nodes))

    if not fixed_nodes:
        raise RuntimeError("Could not find fixed-edge nodes at the right edge.")
    if not hole_boundary_nodes:
        raise RuntimeError("Could not find hole boundary nodes.")
    if not bearing_arc_nodes:
        raise RuntimeError("Could not find bearing arc nodes. Increase hole_tol or bearing_arc_half_width_deg.")

    mesh_text = mesh_inp.read_text(encoding="utf-8", errors="ignore")

    plastic_lines = "\n".join(f"{stress:.6g}, {eps:.6g}" for stress, eps in params.plastic_curve)

    analysis = f"""
**
** ----------------------------------------------------------------
** Added by make_bearing_tearout_demo.py
** Units: inch, kip, ksi
**
** This is a 2D plane-stress bearing/tearout proxy model.
** The left arc of the bolt hole is displaced toward the free edge.
** It predicts stress and PEEQ localization. It does not perform
** literal ductile fracture or automatic element deletion.
** ----------------------------------------------------------------
**
*ELSET, ELSET=EALL
{chunked_int_list(sorted(element_ids)).rstrip()}
*NSET, NSET=FIXED_RIGHT_EDGE
{chunked_int_list(fixed_nodes).rstrip()}
*NSET, NSET=HOLE_BOUNDARY
{chunked_int_list(hole_boundary_nodes).rstrip()}
*NSET, NSET=BEARING_ARC
{chunked_int_list(bearing_arc_nodes).rstrip()}
"""

    if top_ligament_nodes:
        analysis += f"""*NSET, NSET=TOP_TEAROUT_LIGAMENT
{chunked_int_list(top_ligament_nodes).rstrip()}
"""
    if bottom_ligament_nodes:
        analysis += f"""*NSET, NSET=BOTTOM_TEAROUT_LIGAMENT
{chunked_int_list(bottom_ligament_nodes).rstrip()}
"""

    analysis += f"""**
*MATERIAL, NAME=A992_IDEALIZED
*ELASTIC
{params.E:.6g}, {params.nu:.6g}
*PLASTIC
{plastic_lines}
**
*SOLID SECTION, ELSET=EALL, MATERIAL=A992_IDEALIZED
{params.thickness:.6g}
**
*STEP, NAME=BEARING_TEAROUT, NLGEOM=YES, INC=300
*STATIC
0.005, 1.0, 1e-8, 0.025
**
** Right side is the connected/gross-section side.
** The bearing arc on the hole is pushed toward the free edge.
**
** Fixed edge:
*BOUNDARY
FIXED_RIGHT_EDGE, 1, 1, 0.0
FIXED_RIGHT_EDGE, 2, 2, 0.0
FIXED_RIGHT_EDGE, 3, 3, 0.0
**
** Bearing proxy. U1 only is prescribed so the arc can still deform in U2.
** Negative U1 means the bolt pushes/pulls toward the left free edge.
*BOUNDARY
BEARING_ARC, 1, 1, {params.bolt_arc_displacement_x:.6g}
BEARING_ARC, 3, 3, 0.0
**
*NODE FILE
U, RF
*EL FILE
S, E, PE, PEEQ
**
** Reaction output. The total x-reaction on BEARING_ARC estimates bolt load.
*NODE PRINT, NSET=BEARING_ARC, TOTALS=YES
RF
*NODE PRINT, NSET=FIXED_RIGHT_EDGE, TOTALS=YES
RF
*END STEP
"""

    out_ccx_inp.write_text(mesh_text.rstrip() + "\n" + analysis, encoding="utf-8")


def write_readme(params: ModelParams, out_path: Path):
    text = f"""# Bearing and tearout demo for PrePoMax / CalculiX

This package creates a 2D plane-stress finite-element model of an A992-like steel plate/web with one bolt hole near a free edge.

The model is designed to show:

- bearing/crushing near the loaded side of the bolt hole
- plastic strain concentration around the hole
- likely tearout path from the hole to the free edge

## Important limitation

This is not a true fracture simulation. The mesh will not physically split apart. Use the PEEQ field to show the likely tearout initiation and path.

Suggested figure caption:

> Bearing and tearout tendency visualized using equivalent plastic strain localization around the bolt hole. The model does not include element deletion; the high-plastic-strain zone identifies the expected tearout path.

## Files

- `make_bearing_tearout_demo.py`: Python script that generates the mesh and CalculiX input deck
- `run_bearing_tearout.sh`: Linux/Codespaces run script
- `run_bearing_tearout.bat`: Windows run script

## Install dependency

```bash
python3 -m pip install gmsh
```

In Codespaces/Ubuntu, if Gmsh import complains about missing libraries, install:

```bash
sudo apt update
sudo apt install -y calculix-ccx libglu1-mesa libgl1 libglx-mesa0 libxrender1 libxext6 libsm6 libxcursor1 libxinerama1 libxi6 libxrandr2
```

## Generate and run

```bash
python3 make_bearing_tearout_demo.py
ccx bearing_tearout_demo_ccx
```

or:

```bash
chmod +x run_bearing_tearout.sh
./run_bearing_tearout.sh
```

## Open in PrePoMax

After CalculiX finishes, download/open:

```text
bearing_tearout_demo_ccx.frd
```

Plot:

- `PEEQ`
- von Mises stress
- deformed shape

## Key model settings

- Plate length: {params.length} in
- Plate height: {params.height} in
- Plate thickness: {params.thickness} in
- Hole diameter: {params.hole_diameter} in
- Hole center edge distance: {params.hole_center_x} in
- Applied bearing arc displacement: {params.bolt_arc_displacement_x} in
- E: {params.E} ksi
- nu: {params.nu}

## First things to change

Inside `ModelParams`:

```python
length = 8.0
height = 4.0
thickness = 0.375
hole_diameter = 13.0 / 16.0
hole_center_x = 1.25
bolt_arc_displacement_x = -0.18
```

Increase `hole_center_x` to show that larger edge distance reduces tearout tendency.
Decrease `hole_center_x` to make tearout more severe.

For a more dramatic visualization, increase:

```python
bolt_arc_displacement_x = -0.25
```

For an easier first convergence run, reduce it:

```python
bolt_arc_displacement_x = -0.08
```
"""
    out_path.write_text(text, encoding="utf-8")


def write_run_scripts(out_dir: Path):
    sh = """#!/usr/bin/env bash
set -e

python3 make_bearing_tearout_demo.py
ccx bearing_tearout_demo_ccx

echo
echo "Done. Download/open bearing_tearout_demo_ccx.frd in PrePoMax."
ls -lh bearing_tearout_demo_ccx.* 2>/dev/null || true
"""
    bat = """@echo off
echo Generating and running bearing/tearout demo...
py make_bearing_tearout_demo.py
ccx bearing_tearout_demo_ccx
pause
"""
    (out_dir / "run_bearing_tearout.sh").write_text(sh, encoding="utf-8")
    (out_dir / "run_bearing_tearout.bat").write_text(bat, encoding="utf-8")


def main():
    params = ModelParams()

    out_dir = Path(".").resolve()
    mesh_inp = out_dir / "bearing_tearout_demo_mesh.inp"
    ccx_inp = out_dir / "bearing_tearout_demo_ccx.inp"
    brep = out_dir / "bearing_tearout_demo_geometry.brep"
    readme = out_dir / "README_bearing_tearout_demo.md"

    print("Generating Gmsh mesh...")
    make_gmsh_mesh(params, mesh_inp, brep)

    print("Building CalculiX input deck...")
    build_calculix_deck(params, mesh_inp, ccx_inp)

    write_readme(params, readme)
    write_run_scripts(out_dir)

    print("\\nDone.")
    print(f"Mesh file:      {mesh_inp.name}")
    print(f"CalculiX file:  {ccx_inp.name}")
    print(f"Geometry file:  {brep.name}")
    print(f"README:         {readme.name}")
    print("\\nRun:")
    print("    ccx bearing_tearout_demo_ccx")
    print("\\nOpen the .frd results file in PrePoMax after the run.")


if __name__ == "__main__":
    main()
