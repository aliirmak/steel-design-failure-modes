# Steel Failure Mechanism FEA Demos (PrePoMax + CalculiX)

This repository contains small finite element demo models intended for steel design classes.

The goal is to **visualize likely failure mechanisms** (localization/yield patterns) for discussion and teaching, not to produce certified design strengths.

## Important Notes

- This project is intended to show likely failure behavior in steel connection/member examples for classroom use.
- The `prepomax_block_shear_demo_not_good` case is **not ideal at the moment** and should be treated as a work-in-progress demo.
- This project was vibecoded using Codex. Use it at your own risk.
- These are educational nonlinear FE demos, not validated fracture-calibrated production models.

## What Is Included

- `prepomax_a992_web_coupon_rupture`
  - A992-like web coupon with bolt holes in tension; shows stress concentration and rupture tendency via plastic localization.
- `prepomax_bearing_tearout_demo`
  - Single-hole plate near edge; shows bearing/tearout tendency.
- `prepomax_block_shear_demo_not_good`
  - Bolt-group block shear tendency demo (currently not ideal).
- `prepomax_ltb_wsection_demo`
  - W-section lateral-torsional buckling visualization demo.

## Software Stack

- **Model generation**: Python scripts (plus Gmsh for the coupon/tearout/block-shear mesh generation)
- **FE solver**: CalculiX (`ccx`)
- **Results visualization**: **PrePoMax** (primary viewer used)

## Running In GitHub Codespaces

The devcontainer already installs required system packages and Python dependencies (including `calculix-ccx` and `gmsh`) via:

- `.devcontainer/devcontainer.json`

If you open this repo in Codespaces, then:

1. Open a terminal in the repository root.
2. Run one demo folder at a time.

### Quick Run Commands

#### 1) A992 web coupon rupture

```bash
cd prepomax_a992_web_coupon_rupture
python3 make_a992_web_coupon.py
ccx a992_web_coupon_ccx
```

#### 2) Bearing tearout

```bash
cd prepomax_bearing_tearout_demo
python3 make_bearing_tearout_demo.py
ccx bearing_tearout_demo_ccx
```

or:

```bash
cd prepomax_bearing_tearout_demo
chmod +x run_bearing_tearout.sh
./run_bearing_tearout.sh
```

#### 3) Block shear (not ideal currently)

```bash
cd prepomax_block_shear_demo_not_good
python3 make_block_shear_demo.py
ccx block_shear_demo_ccx
```

or:

```bash
cd prepomax_block_shear_demo_not_good
chmod +x run_block_shear.sh
./run_block_shear.sh
```

#### 4) LTB W-section demo

```bash
cd prepomax_ltb_wsection_demo
python3 make_ltb_wsection_demo.py
ccx ltb_wsection_demo_ccx
```

or:

```bash
cd prepomax_ltb_wsection_demo
chmod +x run_ltb_wsection.sh
./run_ltb_wsection.sh
```

## Viewing Results

Each run produces a `.frd` results file (for example, `*_ccx.frd`).

Use **PrePoMax** to open the results and inspect:

- Deformed shape
- von Mises stress
- `PEEQ` equivalent plastic strain

For classroom interpretation, treat high `PEEQ` bands as likely initiation/localization zones, not explicit crack propagation unless a calibrated fracture model is used.

## Suggested Classroom Positioning

These demos are best used to support lecture discussion of:

- net-section rupture tendencies
- bearing and tearout tendencies
- block shear path intuition
- lateral-torsional buckling mechanism visualization

Then compare with code-based hand design checks (for example AISC procedures) as a separate step.
