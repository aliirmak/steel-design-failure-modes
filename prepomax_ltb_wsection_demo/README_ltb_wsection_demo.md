# W-section lateral-torsional buckling demo for PrePoMax / CalculiX

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

- Length: 240.0 in
- Depth: 18.0 in
- Flange width: 6.5 in
- Flange thickness: 0.5 in
- Web thickness: 0.3 in
- Mesh along length: 80
- Mesh across flange width: 12
- Mesh through web depth: 16
- Twist imperfection: 0.02 rad
- Lateral imperfection amplitude: 0.1 in
- Midspan downward displacement: -4.0 in
- Nodes: 3321
- Shell elements: 3200

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
