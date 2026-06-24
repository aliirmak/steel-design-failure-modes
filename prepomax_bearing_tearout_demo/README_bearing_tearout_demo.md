# Bearing and tearout demo for PrePoMax / CalculiX

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

- Plate length: 8.0 in
- Plate height: 4.0 in
- Plate thickness: 0.375 in
- Hole diameter: 0.8125 in
- Hole center edge distance: 1.25 in
- Applied bearing arc displacement: -0.18 in
- E: 29000.0 ksi
- nu: 0.3

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
