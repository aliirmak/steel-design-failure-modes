# A992 web coupon with bolt holes, PrePoMax / CalculiX starter model

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

- Plate length: 24.0 in
- Plate height: 8.0 in
- Plate thickness: 0.3 in
- Hole diameter: 0.8125 in
- Bolt pattern: 2 columns x 3 rows
- Applied displacement: 0.6 in
- E: 29000.0 ksi
- nu: 0.3
- Plastic curve: idealized A992-like stress vs plastic strain

## How to interpret results

Plot:

- von Mises stress
- PEEQ
- deformed shape

A good teaching sentence:

> The simulation does not model physical tearing. The high-PEEQ band indicates the predicted rupture initiation region if ductile fracture were allowed.

For a quick visual rupture flag, look for areas where PEEQ exceeds about 0.15. This is only an assumed visualization threshold, not a calibrated failure model.
