"""
Generate a CalculiX / PrePoMax starter model for an A992 steel web plate
with bolt holes pulled in tension.

What this model does:
- 2D plane-stress web plate
- ASTM A992-like elastic-plastic material
- Displacement-controlled tensile loading
- Outputs stress and equivalent plastic strain (PEEQ)
- Intended to show yielding and likely rupture initiation path, not literal tearing

Units:
- Length: inch
- Stress: ksi
- Force: kip
- Time: arbitrary

Dependencies:
    py -m pip install gmsh

Run:
    py make_a992_web_coupon.py
Then run CalculiX:
    ccx a992_web_coupon_ccx

Or import a992_web_coupon_ccx.inp into PrePoMax and run/open results there.
"""

from __future__ import annotations

from pathlib import Path
from dataclasses import dataclass
import math
import sys


@dataclass
class ModelParams:
    # Geometry, inches
    length: float = 24.0
    height: float = 8.0
    thickness: float = 0.30

    # Bolt-hole pattern, inches
    hole_diameter: float = 13.0 / 16.0   # standard hole for 3/4 in bolt
    n_rows: int = 3
    n_cols: int = 2
    pitch_y: float = 2.5                 # vertical spacing between rows
    gage_x: float = 3.0                  # horizontal spacing between columns
    bolt_group_center_x: float = 12.0
    bolt_group_center_y: float = 0.0

    # Mesh sizes, inches
    mesh_global: float = 0.35
    mesh_near_holes: float = 0.075

    # Loading
    tensile_displacement: float = 0.60   # inches, applied to right edge

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

    # Optional interpretation threshold for postprocessing
    # This is NOT a material failure model. It is only a visual flag.
    assumed_fracture_peeq: float = 0.15


def chunked_int_list(values: list[int], per_line: int = 16) -> str:
    lines = []
    for i in range(0, len(values), per_line):
        lines.append(", ".join(str(v) for v in values[i:i + per_line]))
    return "\n".join(lines) + "\n"


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
    gmsh.model.add("a992_web_coupon")

    L = params.length
    H = params.height
    r = params.hole_diameter / 2.0

    # Rectangle centered vertically about y = 0
    rect = gmsh.model.occ.addRectangle(0.0, -H / 2.0, 0.0, L, H)

    # Hole centers
    hole_centers: list[tuple[float, float]] = []
    x0 = params.bolt_group_center_x - (params.n_cols - 1) * params.gage_x / 2.0
    y0 = params.bolt_group_center_y - (params.n_rows - 1) * params.pitch_y / 2.0

    disks = []
    for i in range(params.n_cols):
        for j in range(params.n_rows):
            x = x0 + i * params.gage_x
            y = y0 + j * params.pitch_y
            hole_centers.append((x, y))
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

    # Identify hole boundary curves for local refinement.
    boundary = gmsh.model.getBoundary([(2, s) for s in surfaces], oriented=False, recursive=False)
    hole_curves = []
    tol = 1.0e-6
    for dim, tag in boundary:
        if dim != 1:
            continue
        xmin, ymin, zmin, xmax, ymax, zmax = gmsh.model.getBoundingBox(dim, tag)
        cx = 0.5 * (xmin + xmax)
        cy = 0.5 * (ymin + ymax)
        # If the curve bbox is inside the plate, it is likely one of the hole boundaries.
        if (xmin > tol and xmax < L - tol and ymin > -H / 2.0 + tol and ymax < H / 2.0 - tol):
            # Extra check: close to one of the hole centers.
            if any(math.hypot(cx - hx, cy - hy) < 1.1 * r for hx, hy in hole_centers):
                hole_curves.append(tag)

    gmsh.option.setNumber("Mesh.MeshSizeMin", params.mesh_near_holes)
    gmsh.option.setNumber("Mesh.MeshSizeMax", params.mesh_global)
    gmsh.option.setNumber("Mesh.Algorithm", 6)  # Frontal-Delaunay for 2D
    gmsh.option.setNumber("Mesh.ElementOrder", 1)
    gmsh.option.setNumber("Mesh.SaveGroupsOfNodes", 1)
    gmsh.option.setNumber("Mesh.SaveAll", 0)

    if hole_curves:
        field_dist = gmsh.model.mesh.field.add("Distance")
        gmsh.model.mesh.field.setNumbers(field_dist, "CurvesList", hole_curves)
        gmsh.model.mesh.field.setNumber(field_dist, "Sampling", 150)

        field_th = gmsh.model.mesh.field.add("Threshold")
        gmsh.model.mesh.field.setNumber(field_th, "InField", field_dist)
        gmsh.model.mesh.field.setNumber(field_th, "SizeMin", params.mesh_near_holes)
        gmsh.model.mesh.field.setNumber(field_th, "SizeMax", params.mesh_global)
        gmsh.model.mesh.field.setNumber(field_th, "DistMin", params.hole_diameter * 0.25)
        gmsh.model.mesh.field.setNumber(field_th, "DistMax", params.hole_diameter * 2.00)
        gmsh.model.mesh.field.setAsBackgroundMesh(field_th)

    gmsh.model.mesh.generate(2)

    # Write an Abaqus/CalculiX-style input mesh.
    gmsh.write(str(out_mesh_inp))

    if out_brep is not None:
        gmsh.write(str(out_brep))

    gmsh.finalize()


def build_calculix_deck(params: ModelParams, mesh_inp: Path, out_ccx_inp: Path):
    nodes, element_ids = read_nodes_and_elements_from_inp(mesh_inp)

    L = params.length
    H = params.height
    coord_tol = max(1.0e-5, params.mesh_near_holes * 0.05)

    fixed_nodes = sorted(nid for nid, (x, y, z) in nodes.items() if abs(x - 0.0) <= coord_tol)
    loaded_nodes = sorted(nid for nid, (x, y, z) in nodes.items() if abs(x - L) <= coord_tol)

    if not fixed_nodes:
        raise RuntimeError("Could not find fixed-edge nodes at x = 0.")
    if not loaded_nodes:
        raise RuntimeError(f"Could not find loaded-edge nodes at x = {L}.")

    mesh_text = mesh_inp.read_text(encoding="utf-8", errors="ignore")

    plastic_lines = "\n".join(f"{stress:.6g}, {eps:.6g}" for stress, eps in params.plastic_curve)

    analysis = f"""
**
** ----------------------------------------------------------------
** Added by make_a992_web_coupon.py
** Units: inch, kip, ksi
** This is a 2D plane-stress model of an A992 steel web plate.
** It predicts stress and PEEQ localization. It does not perform
** literal ductile fracture or automatic element deletion.
** ----------------------------------------------------------------
**
*ELSET, ELSET=EALL
{chunked_int_list(sorted(element_ids)).rstrip()}
*NSET, NSET=FIXED_EDGE
{chunked_int_list(fixed_nodes).rstrip()}
*NSET, NSET=LOADED_EDGE
{chunked_int_list(loaded_nodes).rstrip()}
**
*MATERIAL, NAME=A992_IDEALIZED
*ELASTIC
{params.E:.6g}, {params.nu:.6g}
*PLASTIC
{plastic_lines}
**
*SOLID SECTION, ELSET=EALL, MATERIAL=A992_IDEALIZED
{params.thickness:.6g}
**
*STEP, NAME=TENSION, NLGEOM=YES, INC=300
*STATIC
0.005, 1.0, 1e-8, 0.025
**
** Left end fixed. Right end gripped and pulled in the x direction.
** U2 on loaded edge is restrained to mimic a flat grip and improve stability.
*BOUNDARY
FIXED_EDGE, 1, 1, 0.0
FIXED_EDGE, 2, 2, 0.0
FIXED_EDGE, 3, 3, 0.0
LOADED_EDGE, 1, 1, {params.tensile_displacement:.6g}
LOADED_EDGE, 2, 2, 0.0
LOADED_EDGE, 3, 3, 0.0
**
*NODE FILE
U, RF
*EL FILE
S, E, PE, PEEQ
**
** Reaction output. The total x-reaction on LOADED_EDGE is the applied tensile force.
*NODE PRINT, NSET=LOADED_EDGE, TOTALS=YES
RF
*END STEP
"""

    out_ccx_inp.write_text(mesh_text.rstrip() + "\n" + analysis, encoding="utf-8")


def write_readme(params: ModelParams, out_path: Path):
    text = f"""# A992 web coupon with bolt holes, PrePoMax / CalculiX starter model

This package creates a 2D plane-stress finite-element model of an ASTM A992-like steel web plate with bolt holes and pulls it in tension.

## What it shows

- stress concentration around bolt holes
- yielding around bolt holes
- PEEQ localization along the likely net-section rupture region
- reaction force versus imposed displacement from CalculiX output

## What it does not show

This does not literally tear the mesh apart. CalculiX/PrePoMax is being used here as an elastic-plastic localization demo, not a true ductile fracture/element-deletion model.

## Files

- `make_a992_web_coupon.py`: Python script that generates the mesh and full CalculiX input deck
- `run_ccx.bat`: Windows batch file to run the generated CalculiX model if `ccx` is in PATH

## Install dependency

```bash
py -m pip install gmsh
```

## Generate the model

```bash
py make_a992_web_coupon.py
```

This creates:

- `a992_web_coupon_mesh.inp`
- `a992_web_coupon_ccx.inp`
- `a992_web_coupon_geometry.brep`

## Run with CalculiX

```bash
ccx a992_web_coupon_ccx
```

Do not include `.inp` in the `ccx` command.

## Open in PrePoMax

Option A:
1. Open PrePoMax.
2. File > Import.
3. Import `a992_web_coupon_ccx.inp`.
4. Run the analysis or open the generated `.frd` results file.

Option B:
1. Generate and run the input with `ccx`.
2. Open the resulting `a992_web_coupon_ccx.frd` in PrePoMax.

## Key model settings

- Plate length: {params.length} in
- Plate height: {params.height} in
- Plate thickness: {params.thickness} in
- Hole diameter: {params.hole_diameter} in
- Bolt pattern: {params.n_cols} columns x {params.n_rows} rows
- Applied displacement: {params.tensile_displacement} in
- E: {params.E} ksi
- nu: {params.nu}
- Plastic curve: idealized A992-like stress vs plastic strain

## How to interpret results

Plot:

- von Mises stress
- PEEQ
- deformed shape

A good teaching sentence:

> The simulation does not model physical tearing. The high-PEEQ band indicates the predicted rupture initiation region if ductile fracture were allowed.

For a quick visual rupture flag, look for areas where PEEQ exceeds about {params.assumed_fracture_peeq}. This is only an assumed visualization threshold, not a calibrated failure model.
"""
    out_path.write_text(text, encoding="utf-8")


def write_run_bat(out_path: Path):
    text = """@echo off
echo Running CalculiX model...
echo Make sure ccx.exe is in your PATH, or replace ccx with the full path to ccx.exe.
ccx a992_web_coupon_ccx
pause
"""
    out_path.write_text(text, encoding="utf-8")


def main():
    params = ModelParams()

    out_dir = Path(".").resolve()
    mesh_inp = out_dir / "a992_web_coupon_mesh.inp"
    ccx_inp = out_dir / "a992_web_coupon_ccx.inp"
    brep = out_dir / "a992_web_coupon_geometry.brep"
    readme = out_dir / "README_a992_web_coupon.md"
    bat = out_dir / "run_ccx.bat"

    print("Generating Gmsh mesh...")
    make_gmsh_mesh(params, mesh_inp, brep)

    print("Building CalculiX input deck...")
    build_calculix_deck(params, mesh_inp, ccx_inp)

    write_readme(params, readme)
    write_run_bat(bat)

    print("\nDone.")
    print(f"Mesh file:      {mesh_inp.name}")
    print(f"CalculiX file:  {ccx_inp.name}")
    print(f"Geometry file:  {brep.name}")
    print(f"README:         {readme.name}")
    print("\nRun:")
    print("    ccx a992_web_coupon_ccx")
    print("\nOpen the .frd results file in PrePoMax after the run.")


if __name__ == "__main__":
    main()
