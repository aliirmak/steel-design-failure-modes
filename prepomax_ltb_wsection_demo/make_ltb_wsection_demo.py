"""
Generate a PrePoMax / CalculiX starter model for lateral-torsional
buckling (LTB) of a W-section beam under flexural loading.

This model uses a direct Python-generated shell mesh, so it does NOT need Gmsh.

Run:
    python3 make_ltb_wsection_demo.py
    ccx ltb_wsection_demo_ccx

Open:
    ltb_wsection_demo_ccx.frd
in PrePoMax.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import math


@dataclass
class ModelParams:
    # Beam geometry, inches. Replace with real AISC dimensions if desired.
    length: float = 240.0       # 20 ft unbraced length
    depth: float = 18.0
    flange_width: float = 6.5
    flange_thickness: float = 0.50
    web_thickness: float = 0.30

    # Mesh density
    n_length: int = 80
    n_flange_width: int = 12
    n_web_depth: int = 16

    # Initial imperfection to trigger LTB-like response.
    twist_imperfection_rad: float = 0.020
    lateral_imperfection_amp: float = 0.10  # inches at midspan, scaled by z/z_top

    # Displacement-controlled flexural loading.
    midspan_downward_displacement: float = -4.0

    # Material, ksi
    E: float = 29000.0
    nu: float = 0.30

    # A992-like idealized plastic curve: yield stress ksi, plastic strain.
    plastic_curve: tuple[tuple[float, float], ...] = (
        (50.0, 0.000),
        (55.0, 0.010),
        (60.0, 0.050),
        (65.0, 0.120),
        (70.0, 0.180),
    )


def chunked_int_list(values: list[int], per_line: int = 16) -> str:
    if not values:
        return ""
    lines = []
    for i in range(0, len(values), per_line):
        lines.append(", ".join(str(v) for v in values[i:i + per_line]))
    return "\n".join(lines) + "\n"


def frange_values(a: float, b: float, n: int) -> list[float]:
    if n <= 0:
        return [a]
    return [a + (b - a) * i / n for i in range(n + 1)]


class ShellMeshBuilder:
    def __init__(self, params: ModelParams):
        self.params = params
        self.nodes: dict[tuple[int, int, int], int] = {}
        self.node_coords: dict[int, tuple[float, float, float]] = {}
        self.next_node_id = 1
        self.top_elements: list[tuple[int, int, int, int, int]] = []
        self.bottom_elements: list[tuple[int, int, int, int, int]] = []
        self.web_elements: list[tuple[int, int, int, int, int]] = []
        self.next_element_id = 1
        self.node_tags: dict[int, set[str]] = {}

    @staticmethod
    def qkey(x: float, y: float, z: float) -> tuple[int, int, int]:
        scale = 1_000_000
        return (round(x * scale), round(y * scale), round(z * scale))

    def apply_imperfection(self, x: float, y: float, z: float) -> tuple[float, float, float]:
        p = self.params
        L = p.length
        z_top = p.depth / 2.0 - p.flange_thickness / 2.0
        s = math.sin(math.pi * x / L)
        phi = p.twist_imperfection_rad * s
        y_rot = y * math.cos(phi) - z * math.sin(phi)
        z_rot = y * math.sin(phi) + z * math.cos(phi)
        height_scale = z / z_top if abs(z_top) > 1e-12 else 0.0
        y_rot += p.lateral_imperfection_amp * s * height_scale
        return (x, y_rot, z_rot)

    def get_node(self, x: float, y: float, z: float, tags: tuple[str, ...] = ()) -> int:
        key = self.qkey(x, y, z)
        if key in self.nodes:
            nid = self.nodes[key]
        else:
            nid = self.next_node_id
            self.next_node_id += 1
            self.nodes[key] = nid
            self.node_coords[nid] = self.apply_imperfection(x, y, z)
            self.node_tags[nid] = set()
        self.node_tags[nid].update(tags)
        return nid

    def add_element(self, n1: int, n2: int, n3: int, n4: int, group: str):
        eid = self.next_element_id
        self.next_element_id += 1
        rec = (eid, n1, n2, n3, n4)
        if group == 'top':
            self.top_elements.append(rec)
        elif group == 'bottom':
            self.bottom_elements.append(rec)
        elif group == 'web':
            self.web_elements.append(rec)
        else:
            raise ValueError(group)

    def build(self):
        p = self.params
        L = p.length
        bf = p.flange_width
        d = p.depth
        tf = p.flange_thickness
        z_top = d / 2.0 - tf / 2.0
        z_bot = -d / 2.0 + tf / 2.0
        xs = frange_values(0.0, L, p.n_length)
        ys = frange_values(-bf / 2.0, bf / 2.0, p.n_flange_width)
        zs_web = frange_values(z_bot, z_top, p.n_web_depth)
        mid_i = p.n_length // 2

        # Top flange surface.
        top_grid = []
        for i, x in enumerate(xs):
            row = []
            for y in ys:
                tags = ['ALL']
                if i == 0:
                    tags.append('LEFT_SUPPORT')
                if i == p.n_length:
                    tags.append('RIGHT_SUPPORT')
                if i == mid_i:
                    tags.append('MIDSPAN_TOP_LOAD_LINE')
                if abs(y) < 1e-10:
                    tags.append('TOP_FLANGE_CENTERLINE')
                row.append(self.get_node(x, y, z_top, tuple(tags)))
            top_grid.append(row)
        for i in range(p.n_length):
            for j in range(p.n_flange_width):
                self.add_element(top_grid[i][j], top_grid[i + 1][j], top_grid[i + 1][j + 1], top_grid[i][j + 1], 'top')

        # Bottom flange surface.
        bot_grid = []
        for i, x in enumerate(xs):
            row = []
            for y in ys:
                tags = ['ALL']
                if i == 0:
                    tags.append('LEFT_SUPPORT')
                if i == p.n_length:
                    tags.append('RIGHT_SUPPORT')
                if abs(y) < 1e-10:
                    tags.append('BOTTOM_FLANGE_CENTERLINE')
                row.append(self.get_node(x, y, z_bot, tuple(tags)))
            bot_grid.append(row)
        for i in range(p.n_length):
            for j in range(p.n_flange_width):
                # Reversed order to keep a sensible normal for bottom surface.
                self.add_element(bot_grid[i][j], bot_grid[i][j + 1], bot_grid[i + 1][j + 1], bot_grid[i + 1][j], 'bottom')

        # Web surface, y = 0.
        web_grid = []
        for i, x in enumerate(xs):
            col = []
            for z in zs_web:
                tags = ['ALL']
                if i == 0:
                    tags.append('LEFT_SUPPORT')
                if i == p.n_length:
                    tags.append('RIGHT_SUPPORT')
                if i == 0 and abs(z) < 1e-10:
                    tags.append('LEFT_WEB_MID_ANCHOR')
                if i == p.n_length and abs(z) < 1e-10:
                    tags.append('RIGHT_WEB_MID')
                if i == mid_i and abs(z) < 1e-10:
                    tags.append('MIDSPAN_WEB_MID')
                col.append(self.get_node(x, 0.0, z, tuple(tags)))
            web_grid.append(col)
        for i in range(p.n_length):
            for k in range(p.n_web_depth):
                self.add_element(web_grid[i][k], web_grid[i + 1][k], web_grid[i + 1][k + 1], web_grid[i][k + 1], 'web')

    def nset(self, name: str) -> list[int]:
        return sorted(nid for nid, tags in self.node_tags.items() if name in tags)

    def all_elements(self) -> list[int]:
        return sorted([e[0] for e in self.top_elements] + [e[0] for e in self.bottom_elements] + [e[0] for e in self.web_elements])


def write_inp(params: ModelParams, out_path: Path):
    mesh = ShellMeshBuilder(params)
    mesh.build()
    plastic_lines = "\n".join(f"{s:.6g}, {e:.6g}" for s, e in params.plastic_curve)
    top_eids = [e[0] for e in mesh.top_elements]
    bot_eids = [e[0] for e in mesh.bottom_elements]
    all_eids = mesh.all_elements()
    left_support = mesh.nset('LEFT_SUPPORT')
    right_support = mesh.nset('RIGHT_SUPPORT')
    left_anchor = mesh.nset('LEFT_WEB_MID_ANCHOR')
    load_line = mesh.nset('MIDSPAN_TOP_LOAD_LINE')
    midspan_web_mid = mesh.nset('MIDSPAN_WEB_MID')
    if not left_anchor:
        candidates = []
        for nid in left_support:
            x, y, z = mesh.node_coords[nid]
            candidates.append((abs(y) + abs(z), nid))
        candidates.sort()
        left_anchor = [candidates[0][1]]

    lines = []
    lines += [
        '**',
        '** W-section lateral-torsional buckling demo',
        '** Generated by make_ltb_wsection_demo.py',
        '** Units: inch, kip, ksi',
        '** This is an imperfect nonlinear static shell model, not a code design check.',
        '**',
        f'** Length = {params.length:.6g} in',
        f'** Depth = {params.depth:.6g} in',
        f'** Flange width = {params.flange_width:.6g} in',
        f'** Flange thickness = {params.flange_thickness:.6g} in',
        f'** Web thickness = {params.web_thickness:.6g} in',
        f'** Twist imperfection amplitude = {params.twist_imperfection_rad:.6g} rad',
        f'** Lateral imperfection amplitude = {params.lateral_imperfection_amp:.6g} in',
        '**',
        '*NODE',
    ]
    for nid in sorted(mesh.node_coords):
        x, y, z = mesh.node_coords[nid]
        lines.append(f'{nid}, {x:.8f}, {y:.8f}, {z:.8f}')

    def elem_block(name, elems):
        lines.append(f'*ELEMENT, TYPE=S4, ELSET={name}')
        for eid, n1, n2, n3, n4 in elems:
            lines.append(f'{eid}, {n1}, {n2}, {n3}, {n4}')

    elem_block('TOP_FLANGE', mesh.top_elements)
    elem_block('BOTTOM_FLANGE', mesh.bottom_elements)
    elem_block('WEB', mesh.web_elements)

    lines.append('*ELSET, ELSET=FLANGES')
    lines.append(chunked_int_list(sorted(top_eids + bot_eids)).rstrip())
    lines.append('*ELSET, ELSET=EALL')
    lines.append(chunked_int_list(all_eids).rstrip())

    def nset(name, values):
        lines.append(f'*NSET, NSET={name}')
        lines.append(chunked_int_list(values).rstrip())

    nset('LEFT_SUPPORT', left_support)
    nset('RIGHT_SUPPORT', right_support)
    nset('LEFT_WEB_MID_ANCHOR', left_anchor)
    nset('MIDSPAN_TOP_LOAD_LINE', load_line)
    nset('MIDSPAN_WEB_MID', midspan_web_mid)

    lines += [
        '**',
        '*MATERIAL, NAME=A992_IDEALIZED',
        '*ELASTIC',
        f'{params.E:.6g}, {params.nu:.6g}',
        '*PLASTIC',
        plastic_lines,
        '**',
        '*SHELL SECTION, ELSET=TOP_FLANGE, MATERIAL=A992_IDEALIZED',
        f'{params.flange_thickness:.6g}',
        '*SHELL SECTION, ELSET=BOTTOM_FLANGE, MATERIAL=A992_IDEALIZED',
        f'{params.flange_thickness:.6g}',
        '*SHELL SECTION, ELSET=WEB, MATERIAL=A992_IDEALIZED',
        f'{params.web_thickness:.6g}',
        '**',
        '*STEP, NAME=LTB_BENDING, NLGEOM=YES, INC=300',
        '*STATIC',
        '0.005, 1.0, 1e-8, 0.020',
        '** End-braced simply-supported style constraints.',
        '** U2 = lateral displacement, U3 = vertical displacement.',
        '*BOUNDARY',
        'LEFT_SUPPORT, 2, 2, 0.0',
        'RIGHT_SUPPORT, 2, 2, 0.0',
        'LEFT_SUPPORT, 3, 3, 0.0',
        'RIGHT_SUPPORT, 3, 3, 0.0',
        'LEFT_WEB_MID_ANCHOR, 1, 1, 0.0',
        '** Displacement-controlled flexural loading at top flange midspan.',
        '*BOUNDARY',
        f'MIDSPAN_TOP_LOAD_LINE, 3, 3, {params.midspan_downward_displacement:.6g}',
        '**',
        '*NODE FILE',
        'U, RF',
        '*EL FILE',
        'S, E, PE, PEEQ',
        '**',
        '*NODE PRINT, NSET=MIDSPAN_TOP_LOAD_LINE, TOTALS=YES',
        'RF',
        '*NODE PRINT, NSET=LEFT_SUPPORT, TOTALS=YES',
        'RF',
        '*NODE PRINT, NSET=RIGHT_SUPPORT, TOTALS=YES',
        'RF',
        '*END STEP',
        '',
    ]
    out_path.write_text('\n'.join(lines), encoding='utf-8')
    return {
        'nodes': len(mesh.node_coords),
        'elements': len(all_eids),
        'top_elements': len(top_eids),
        'bottom_elements': len(bot_eids),
        'web_elements': len([e[0] for e in mesh.web_elements]),
        'load_nodes': len(load_line),
        'left_support_nodes': len(left_support),
        'right_support_nodes': len(right_support),
    }


def write_readme(params: ModelParams, stats: dict[str, int], out_path: Path):
    text = f"""# W-section lateral-torsional buckling demo for PrePoMax / CalculiX

This package creates a shell-element W-section beam model intended to show lateral-torsional buckling behavior under flexural loading.

## What this model shows

- major-axis flexural deformation
- lateral movement of the compression flange
- twisting of the cross-section
- LTB-like deformation triggered by a small initial imperfection

## Important limitation

This is a teaching/demo model, not a design-strength calculation. It is an imperfect nonlinear static shell model. Use it to visualize the LTB mechanism, then compare with AISC lateral-torsional buckling calculations separately.

It is not an eigenvalue buckling model and it is not calibrated for a specific W-shape unless you replace the dimensions with your actual section dimensions.

## Why no Gmsh?

This model generates the shell mesh directly in Python, so Codespaces only needs Python and CalculiX. No Gmsh/OpenGL dependency.

## Run in Codespaces

Install CalculiX if needed:

```bash
sudo apt update
sudo apt install -y calculix-ccx
```

Generate and run:

```bash
chmod +x run_ltb_wsection.sh
./run_ltb_wsection.sh
```

or manually:

```bash
python3 make_ltb_wsection_demo.py
ccx ltb_wsection_demo_ccx
```

Open/download:

```text
ltb_wsection_demo_ccx.frd
```

in PrePoMax.

## What to plot in PrePoMax

Start with:

```text
Deformed shape
U2 lateral displacement
U3 vertical displacement
S, especially longitudinal stress
```

If the imposed displacement is large enough to cause yielding, also plot:

```text
PEEQ
```

For a clean LTB mechanism figure, show the deformed shape with a deformation scale of about 1 to 3. If it is subtle, increase the display scale in PrePoMax before increasing the actual imposed displacement.

## Current model settings

- Length: {params.length} in
- Depth: {params.depth} in
- Flange width: {params.flange_width} in
- Flange thickness: {params.flange_thickness} in
- Web thickness: {params.web_thickness} in
- Mesh along length: {params.n_length}
- Mesh across flange width: {params.n_flange_width}
- Mesh through web depth: {params.n_web_depth}
- Twist imperfection: {params.twist_imperfection_rad} rad
- Lateral imperfection amplitude: {params.lateral_imperfection_amp} in
- Midspan downward displacement: {params.midspan_downward_displacement} in
- Nodes: {stats['nodes']}
- Shell elements: {stats['elements']}

## Parameters to modify

Inside `make_ltb_wsection_demo.py`, edit `ModelParams`.

To make the LTB deformation more visible:

```python
twist_imperfection_rad = 0.040
lateral_imperfection_amp = 0.25
midspan_downward_displacement = -5.0
```

To make the model gentler and more elastic:

```python
twist_imperfection_rad = 0.010
lateral_imperfection_amp = 0.05
midspan_downward_displacement = -1.5
```

To represent a different W-section:

```python
depth = 18.0
flange_width = 6.5
flange_thickness = 0.50
web_thickness = 0.30
```

For example, replace those with the actual AISC dimensions for your W-shape.

## Suggested caption

> Lateral-torsional buckling mechanism of an unbraced W-section under flexural loading, visualized using an imperfect nonlinear shell model. The compression flange moves laterally while the cross-section twists, illustrating the coupled lateral bending and torsional response.

## Notes on boundary conditions

The beam ends are vertically supported and laterally braced:

```text
U2 = 0 at both ends
U3 = 0 at both ends
U1 = 0 at one web-mid node to prevent axial rigid-body motion
```

The midspan top flange line receives a downward prescribed displacement. This is more robust than force control for a first demo.
"""
    out_path.write_text(text, encoding='utf-8')


def write_run_scripts(out_dir: Path):
    sh = """#!/usr/bin/env bash
set -e

python3 make_ltb_wsection_demo.py
ccx ltb_wsection_demo_ccx

echo
echo \"Done. Download/open ltb_wsection_demo_ccx.frd in PrePoMax.\"
ls -lh ltb_wsection_demo_ccx.* 2>/dev/null || true
"""
    bat = """@echo off
echo Generating and running W-section LTB demo...
py make_ltb_wsection_demo.py
ccx ltb_wsection_demo_ccx
pause
"""
    (out_dir / 'run_ltb_wsection.sh').write_text(sh, encoding='utf-8')
    (out_dir / 'run_ltb_wsection.bat').write_text(bat, encoding='utf-8')


def main():
    params = ModelParams()
    out_dir = Path('.').resolve()
    inp = out_dir / 'ltb_wsection_demo_ccx.inp'
    readme = out_dir / 'README_ltb_wsection_demo.md'
    print('Generating shell mesh and CalculiX input deck...')
    stats = write_inp(params, inp)
    write_readme(params, stats, readme)
    write_run_scripts(out_dir)
    print('\nDone.')
    print(f'CalculiX file: {inp.name}')
    print(f'README:        {readme.name}')
    print('\nModel size:')
    for key, value in stats.items():
        print(f'  {key}: {value}')
    print('\nRun:')
    print('    ccx ltb_wsection_demo_ccx')
    print('\nOpen the .frd results file in PrePoMax after the run.')


if __name__ == '__main__':
    main()
