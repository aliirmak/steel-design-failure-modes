"""
Generate a CalculiX / PrePoMax starter model for block shear around
a bolt group in an A992 steel plate/web.

This is a robust "block shear proxy" model:
- 2D plane-stress plate
- rectangular bolt group near the free end
- right edge is pulled in tension
- selected bearing arcs on the holes are restrained to mimic bolts/gusset
- plastic strain localization indicates likely block shear path

Expected visual pattern:
- shear bands roughly parallel to the load, from the bolt group toward the free edge
- tensile band across the inner bolt line
- high PEEQ around bolt holes and along the block-shear path

This model intentionally avoids full contact for the first version. Full bolt-hole
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
    py make_block_shear_demo.py
Then run CalculiX:
    ccx block_shear_demo_ccx

Or import block_shear_demo_ccx.inp into PrePoMax and run/open results there.
"""

from __future__ import annotations

from pathlib import Path
from dataclasses import dataclass
import math
import sys


@dataclass
class ModelParams:
    # Geometry, inches
    # Plate represents a W-shape web/plate strip near a bolted connection.
    length: float = 10.0
    height: float = 6.0
    thickness: float = 0.375

    # Bolt-hole group, inches
    hole_diameter: float = 13.0 / 16.0      # standard hole for 3/4 in bolt
    n_cols_along_load: int = 2              # columns in x direction
    n_rows_transverse: int = 3              # rows in y direction
    first_col_x: float = 1.35               # distance from free edge to first bolt column
    col_pitch_x: float = 2.00               # spacing along load
    row_pitch_y: float = 1.75               # spacing transverse to load
    bolt_group_center_y: float = 0.0

    # Bearing/support arc:
    # For a plate pulled to the right while bolts restrain it,
    # the bearing contact is approximated on the left side of each hole.
    # 180 degrees = left side of the circular hole.
    bearing_arc_center_angle_deg: float = 180.0
    bearing_arc_half_width_deg: float = 55.0

    # Mesh sizes, inches
    mesh_global: float = 0.25
    mesh_near_holes: float = 0.040
    mesh_block_region: float = 0.065

    # Loading
    tensile_displacement_right_edge: float = 0.28

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
    assumed_block_shear_peeq: float = 0.15


def chunked_int_list(values: list[int], per_line: int = 16) -> str:
    lines = []
    for i in range(0, len(values), per_line):
        lines.append(", ".join(str(v) for v in values[i:i + per_line]))
    return "\n".join(lines) + "\n"


def angle_distance_deg(a: float, b: float) -> float:
    """Smallest absolute distance between two angles in degrees."""
    return abs((a - b + 180.0) % 360.0 - 180.0)


def hole_centers(params: ModelParams) -> list[tuple[float, float]]:
    y0 = params.bolt_group_center_y - (params.n_rows_transverse - 1) * params.row_pitch_y / 2.0
    centers = []
    for i in range(params.n_cols_along_load):
        x = params.first_col_x + i * params.col_pitch_x
        for j in range(params.n_rows_transverse):
            y = y0 + j * params.row_pitch_y
            centers.append((x, y))
    return centers


def block_geometry_summary(params: ModelParams) -> dict[str, float]:
    """Approximate geometric quantities for a teaching block-shear check.

    These are not a full AISC design calculation. They are printed so that
    the FE visualization can be compared to the classic block-shear idea.
    """
    centers = hole_centers(params)
    xs = sorted(set(round(x, 10) for x, y in centers))
    ys = sorted(set(round(y, 10) for x, y in centers))

    r = params.hole_diameter / 2.0
    left_edge = 0.0
    inner_col_x = max(xs)
    top_shear_y = max(ys) + r
    bottom_shear_y = min(ys) - r
    block_height = top_shear_y - bottom_shear_y
    shear_plane_length_each = inner_col_x - left_edge
    total_gross_shear_area = 2.0 * shear_plane_length_each * params.thickness
    gross_tension_area = block_height * params.thickness

    # Very simplified net tension plane estimate: subtract holes on the inner column.
    net_tension_area_simple = max(block_height - params.n_rows_transverse * params.hole_diameter, 0.0) * params.thickness

    return {
        "inner_col_x": inner_col_x,
        "top_shear_y": top_shear_y,
        "bottom_shear_y": bottom_shear_y,
        "block_height": block_height,
        "shear_plane_length_each": shear_plane_length_each,
        "total_gross_shear_area": total_gross_shear_area,
        "gross_tension_area": gross_tension_area,
        "net_tension_area_simple": net_tension_area_simple,
    }


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
    gmsh.model.add("block_shear_demo")

    L = params.length
    H = params.height
    r = params.hole_diameter / 2.0
    centers = hole_centers(params)
    summary = block_geometry_summary(params)

    # Rectangle centered vertically about y = 0
    rect = gmsh.model.occ.addRectangle(0.0, -H / 2.0, 0.0, L, H)

    disks = []
    for x, y in centers:
        disks.append(gmsh.model.occ.addDisk(x, y, 0.0, r, r))

    # Cut holes from plate
    cut_result, _ = gmsh.model.occ.cut(
        [(2, rect)],
        [(2, d) for d in disks],
        removeObject=True,
        removeTool=True,
    )
    gmsh.model.occ.synchronize()

    surfaces = [tag for dim, tag in cut_result if dim == 2]
    if not surfaces:
        raise RuntimeError("No plate surface was created after cutting holes.")

    gmsh.model.addPhysicalGroup(2, surfaces, 1)
    gmsh.model.setPhysicalName(2, 1, "PLATE")

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

        # Hole boundary curves are inside the plate and close to a hole center.
        if (xmin > tol and xmax < L - tol and ymin > -H / 2.0 + tol and ymax < H / 2.0 - tol):
            if any(math.hypot(cx - hx, cy - hy) < 1.1 * r for hx, hy in centers):
                hole_curves.append(tag)

        # Free end where the block-shear tearout block would exit.
        if abs(xmin - 0.0) < tol and abs(xmax - 0.0) < tol:
            left_edge_curves.append(tag)

    gmsh.option.setNumber("Mesh.MeshSizeMin", params.mesh_near_holes)
    gmsh.option.setNumber("Mesh.MeshSizeMax", params.mesh_global)
    gmsh.option.setNumber("Mesh.Algorithm", 6)  # Frontal-Delaunay for 2D
    gmsh.option.setNumber("Mesh.ElementOrder", 1)
    gmsh.option.setNumber("Mesh.SaveGroupsOfNodes", 1)
    gmsh.option.setNumber("Mesh.SaveAll", 0)

    fields = []

    if hole_curves:
        field_dist = gmsh.model.mesh.field.add("Distance")
        gmsh.model.mesh.field.setNumbers(field_dist, "CurvesList", hole_curves)
        gmsh.model.mesh.field.setNumber(field_dist, "Sampling", 250)

        field_th = gmsh.model.mesh.field.add("Threshold")
        gmsh.model.mesh.field.setNumber(field_th, "InField", field_dist)
        gmsh.model.mesh.field.setNumber(field_th, "SizeMin", params.mesh_near_holes)
        gmsh.model.mesh.field.setNumber(field_th, "SizeMax", params.mesh_global)
        gmsh.model.mesh.field.setNumber(field_th, "DistMin", params.hole_diameter * 0.20)
        gmsh.model.mesh.field.setNumber(field_th, "DistMax", params.hole_diameter * 1.75)
        fields.append(field_th)

    if left_edge_curves:
        field_dist2 = gmsh.model.mesh.field.add("Distance")
        gmsh.model.mesh.field.setNumbers(field_dist2, "CurvesList", left_edge_curves)
        gmsh.model.mesh.field.setNumber(field_dist2, "Sampling", 120)

        field_th2 = gmsh.model.mesh.field.add("Threshold")
        gmsh.model.mesh.field.setNumber(field_th2, "InField", field_dist2)
        gmsh.model.mesh.field.setNumber(field_th2, "SizeMin", params.mesh_block_region)
        gmsh.model.mesh.field.setNumber(field_th2, "SizeMax", params.mesh_global)
        gmsh.model.mesh.field.setNumber(field_th2, "DistMin", 0.25)
        gmsh.model.mesh.field.setNumber(field_th2, "DistMax", summary["inner_col_x"] + 0.60)
        fields.append(field_th2)

    # Refine the rectangular block-shear region: from left edge to inner bolt column,
    # around the top and bottom shear paths and the tension plane.
    field_box = gmsh.model.mesh.field.add("Box")
    gmsh.model.mesh.field.setNumber(field_box, "VIn", params.mesh_block_region)
    gmsh.model.mesh.field.setNumber(field_box, "VOut", params.mesh_global)
    gmsh.model.mesh.field.setNumber(field_box, "XMin", 0.0)
    gmsh.model.mesh.field.setNumber(field_box, "XMax", summary["inner_col_x"] + 0.55)
    gmsh.model.mesh.field.setNumber(field_box, "YMin", summary["bottom_shear_y"] - 0.40)
    gmsh.model.mesh.field.setNumber(field_box, "YMax", summary["top_shear_y"] + 0.40)
    gmsh.model.mesh.field.setNumber(field_box, "ZMin", -0.1)
    gmsh.model.mesh.field.setNumber(field_box, "ZMax", 0.1)
    fields.append(field_box)

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
    centers = hole_centers(params)
    summary = block_geometry_summary(params)
    r = params.hole_diameter / 2.0

    coord_tol = max(1.0e-5, params.mesh_near_holes * 0.10)
    hole_tol = max(0.01, params.mesh_near_holes * 0.80)

    right_edge_nodes = sorted(nid for nid, (x, y, z) in nodes.items() if abs(x - L) <= coord_tol)
    left_edge_nodes = sorted(nid for nid, (x, y, z) in nodes.items() if abs(x - 0.0) <= coord_tol)

    hole_boundary_nodes = []
    bearing_arc_nodes = []

    top_shear_path_nodes = []
    bottom_shear_path_nodes = []
    tension_plane_nodes = []

    for nid, (x, y, z) in nodes.items():
        # Hole/bearing nodes
        for hx, hy in centers:
            dist = math.hypot(x - hx, y - hy)
            if abs(dist - r) <= hole_tol:
                hole_boundary_nodes.append(nid)
                theta = math.degrees(math.atan2(y - hy, x - hx)) % 360.0
                if angle_distance_deg(theta, params.bearing_arc_center_angle_deg) <= params.bearing_arc_half_width_deg:
                    bearing_arc_nodes.append(nid)
                break

        # Approximate path node sets for easy selection in PrePoMax.
        if 0.0 <= x <= summary["inner_col_x"] + params.mesh_block_region:
            if abs(y - summary["top_shear_y"]) <= params.mesh_block_region * 0.9:
                top_shear_path_nodes.append(nid)
            if abs(y - summary["bottom_shear_y"]) <= params.mesh_block_region * 0.9:
                bottom_shear_path_nodes.append(nid)

        if abs(x - summary["inner_col_x"]) <= params.mesh_block_region * 0.9:
            if summary["bottom_shear_y"] <= y <= summary["top_shear_y"]:
                tension_plane_nodes.append(nid)

    right_edge_nodes = sorted(set(right_edge_nodes))
    left_edge_nodes = sorted(set(left_edge_nodes))
    hole_boundary_nodes = sorted(set(hole_boundary_nodes))
    bearing_arc_nodes = sorted(set(bearing_arc_nodes))
    top_shear_path_nodes = sorted(set(top_shear_path_nodes))
    bottom_shear_path_nodes = sorted(set(bottom_shear_path_nodes))
    tension_plane_nodes = sorted(set(tension_plane_nodes))

    if not right_edge_nodes:
        raise RuntimeError("Could not find right-edge loaded nodes.")
    if not hole_boundary_nodes:
        raise RuntimeError("Could not find hole boundary nodes.")
    if not bearing_arc_nodes:
        raise RuntimeError("Could not find bearing arc nodes. Increase hole_tol or bearing_arc_half_width_deg.")

    mesh_text = mesh_inp.read_text(encoding="utf-8", errors="ignore")
    plastic_lines = "\n".join(f"{stress:.6g}, {eps:.6g}" for stress, eps in params.plastic_curve)

    analysis = f"""
**
** ----------------------------------------------------------------
** Added by make_block_shear_demo.py
** Units: inch, kip, ksi
**
** This is a 2D plane-stress block-shear proxy model.
** Right edge is pulled in tension.
** Bearing arcs on the holes are restrained to mimic bolts/gusset support.
** It predicts stress and PEEQ localization. It does not perform
** literal ductile fracture or automatic element deletion.
**
** Approximate block-shear guide geometry:
**   inner bolt column x             = {summary["inner_col_x"]:.6g} in
**   top shear path y                = {summary["top_shear_y"]:.6g} in
**   bottom shear path y             = {summary["bottom_shear_y"]:.6g} in
**   block height                    = {summary["block_height"]:.6g} in
**   each gross shear length         = {summary["shear_plane_length_each"]:.6g} in
**   total gross shear area proxy    = {summary["total_gross_shear_area"]:.6g} in^2
**   gross tension area proxy        = {summary["gross_tension_area"]:.6g} in^2
**   simple net tension area proxy   = {summary["net_tension_area_simple"]:.6g} in^2
** ----------------------------------------------------------------
**
*ELSET, ELSET=EALL
{chunked_int_list(sorted(element_ids)).rstrip()}
*NSET, NSET=RIGHT_LOADED_EDGE
{chunked_int_list(right_edge_nodes).rstrip()}
*NSET, NSET=LEFT_FREE_EDGE
{chunked_int_list(left_edge_nodes).rstrip()}
*NSET, NSET=HOLE_BOUNDARY
{chunked_int_list(hole_boundary_nodes).rstrip()}
*NSET, NSET=BEARING_ARCS
{chunked_int_list(bearing_arc_nodes).rstrip()}
"""

    if top_shear_path_nodes:
        analysis += f"""*NSET, NSET=TOP_SHEAR_PATH_GUIDE
{chunked_int_list(top_shear_path_nodes).rstrip()}
"""
    if bottom_shear_path_nodes:
        analysis += f"""*NSET, NSET=BOTTOM_SHEAR_PATH_GUIDE
{chunked_int_list(bottom_shear_path_nodes).rstrip()}
"""
    if tension_plane_nodes:
        analysis += f"""*NSET, NSET=TENSION_PLANE_GUIDE
{chunked_int_list(tension_plane_nodes).rstrip()}
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
*STEP, NAME=BLOCK_SHEAR, NLGEOM=YES, INC=350
*STATIC
0.0025, 1.0, 1e-8, 0.020
**
** Bolt/gusset proxy:
** The left bearing arcs of the holes are restrained in U1.
** U2 is left free so the plate can deform around the bolts.
*BOUNDARY
BEARING_ARCS, 1, 1, 0.0
BEARING_ARCS, 3, 3, 0.0
**
** Right edge is displacement-controlled in tension.
** U2 is fixed on the gripped edge to keep the grip flat and stable.
*BOUNDARY
RIGHT_LOADED_EDGE, 1, 1, {params.tensile_displacement_right_edge:.6g}
RIGHT_LOADED_EDGE, 2, 2, 0.0
RIGHT_LOADED_EDGE, 3, 3, 0.0
**
*NODE FILE
U, RF
*EL FILE
S, E, PE, PEEQ
**
** Reaction output.
** Total x-reaction on RIGHT_LOADED_EDGE estimates applied tensile load.
** Total x-reaction on BEARING_ARCS estimates bolt-group reaction.
*NODE PRINT, NSET=RIGHT_LOADED_EDGE, TOTALS=YES
RF
*NODE PRINT, NSET=BEARING_ARCS, TOTALS=YES
RF
*END STEP
"""

    out_ccx_inp.write_text(mesh_text.rstrip() + "\n" + analysis, encoding="utf-8")


def write_readme(params: ModelParams, out_path: Path):
    summary = block_geometry_summary(params)

    text = f"""# Block shear demo for PrePoMax / CalculiX

This package creates a 2D plane-stress finite-element model of an A992-like steel plate/web with a rectangular bolt group near a free edge.

The model is designed to show:

- bolt bearing stress concentration
- block-shear type plastic strain localization
- two shear-dominated paths parallel to the load
- one tension-dominated path across the inner bolt line

## Important limitation

This is not a true fracture simulation. The mesh will not physically split apart. Use the PEEQ field to show the likely block-shear initiation and path.

Suggested figure caption:

> Block shear tendency visualized using equivalent plastic strain localization around the bolt group. The model does not include element deletion; the high-plastic-strain zones identify the expected shear and tension portions of the block-shear path.

## Files

- `make_block_shear_demo.py`: Python script that generates the mesh and CalculiX input deck
- `run_block_shear.sh`: Linux/Codespaces run script
- `run_block_shear.bat`: Windows run script

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
python3 make_block_shear_demo.py
ccx block_shear_demo_ccx
```

or:

```bash
chmod +x run_block_shear.sh
./run_block_shear.sh
```

## Open in PrePoMax

After CalculiX finishes, download/open:

```text
block_shear_demo_ccx.frd
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
- Bolt group: {params.n_cols_along_load} columns x {params.n_rows_transverse} rows
- First bolt column from free edge: {params.first_col_x} in
- Column pitch along load: {params.col_pitch_x} in
- Row pitch transverse to load: {params.row_pitch_y} in
- Right-edge displacement: {params.tensile_displacement_right_edge} in
- E: {params.E} ksi
- nu: {params.nu}

## Approximate block-shear guide geometry

These values are only for teaching interpretation, not a full AISC design check.

- Inner bolt column x: {summary["inner_col_x"]:.4f} in
- Top shear path y: {summary["top_shear_y"]:.4f} in
- Bottom shear path y: {summary["bottom_shear_y"]:.4f} in
- Each gross shear path length: {summary["shear_plane_length_each"]:.4f} in
- Total gross shear area proxy: {summary["total_gross_shear_area"]:.4f} in²
- Gross tension area proxy: {summary["gross_tension_area"]:.4f} in²
- Simple net tension area proxy: {summary["net_tension_area_simple"]:.4f} in²

## First things to change

Inside `ModelParams`:

```python
length = 10.0
height = 6.0
thickness = 0.375
hole_diameter = 13.0 / 16.0
n_cols_along_load = 2
n_rows_transverse = 3
first_col_x = 1.35
col_pitch_x = 2.00
row_pitch_y = 1.75
tensile_displacement_right_edge = 0.28
```

To make block shear more severe:

```python
first_col_x = 1.00
col_pitch_x = 1.50
tensile_displacement_right_edge = 0.35
```

To make it less severe:

```python
first_col_x = 1.75
col_pitch_x = 2.50
tensile_displacement_right_edge = 0.15
```

The main story is the PEEQ pattern:

```text
top shear path + bottom shear path + tension plane across the inner bolt line
```
"""
    out_path.write_text(text, encoding="utf-8")


def write_run_scripts(out_dir: Path):
    sh = """#!/usr/bin/env bash
set -e

python3 make_block_shear_demo.py
ccx block_shear_demo_ccx

echo
echo "Done. Download/open block_shear_demo_ccx.frd in PrePoMax."
ls -lh block_shear_demo_ccx.* 2>/dev/null || true
"""
    bat = """@echo off
echo Generating and running block shear demo...
py make_block_shear_demo.py
ccx block_shear_demo_ccx
pause
"""
    (out_dir / "run_block_shear.sh").write_text(sh, encoding="utf-8")
    (out_dir / "run_block_shear.bat").write_text(bat, encoding="utf-8")


def main():
    params = ModelParams()

    out_dir = Path(".").resolve()
    mesh_inp = out_dir / "block_shear_demo_mesh.inp"
    ccx_inp = out_dir / "block_shear_demo_ccx.inp"
    brep = out_dir / "block_shear_demo_geometry.brep"
    readme = out_dir / "README_block_shear_demo.md"

    print("Generating Gmsh mesh...")
    make_gmsh_mesh(params, mesh_inp, brep)

    print("Building CalculiX input deck...")
    build_calculix_deck(params, mesh_inp, ccx_inp)

    write_readme(params, readme)
    write_run_scripts(out_dir)

    summary = block_geometry_summary(params)

    print("\\nDone.")
    print(f"Mesh file:      {mesh_inp.name}")
    print(f"CalculiX file:  {ccx_inp.name}")
    print(f"Geometry file:  {brep.name}")
    print(f"README:         {readme.name}")

    print("\\nApproximate block-shear guide geometry:")
    print(f"  inner bolt column x:           {summary['inner_col_x']:.4f} in")
    print(f"  top shear path y:              {summary['top_shear_y']:.4f} in")
    print(f"  bottom shear path y:           {summary['bottom_shear_y']:.4f} in")
    print(f"  each gross shear path length:  {summary['shear_plane_length_each']:.4f} in")
    print(f"  total gross shear area proxy:  {summary['total_gross_shear_area']:.4f} in^2")
    print(f"  simple net tension area proxy: {summary['net_tension_area_simple']:.4f} in^2")

    print("\\nRun:")
    print("    ccx block_shear_demo_ccx")
    print("\\nOpen the .frd results file in PrePoMax after the run.")


if __name__ == "__main__":
    main()
