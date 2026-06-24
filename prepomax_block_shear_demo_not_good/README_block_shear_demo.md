# Block shear demo for PrePoMax / CalculiX

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

- Plate length: 10.0 in
- Plate height: 6.0 in
- Plate thickness: 0.375 in
- Hole diameter: 0.8125 in
- Bolt group: 2 columns x 3 rows
- First bolt column from free edge: 1.35 in
- Column pitch along load: 2.0 in
- Row pitch transverse to load: 1.75 in
- Right-edge displacement: 0.28 in
- E: 29000.0 ksi
- nu: 0.3

## Approximate block-shear guide geometry

These values are only for teaching interpretation, not a full AISC design check.

- Inner bolt column x: 3.3500 in
- Top shear path y: 2.1562 in
- Bottom shear path y: -2.1562 in
- Each gross shear path length: 3.3500 in
- Total gross shear area proxy: 2.5125 in²
- Gross tension area proxy: 1.6172 in²
- Simple net tension area proxy: 0.7031 in²

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
