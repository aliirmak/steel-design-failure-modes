#!/usr/bin/env bash
set -e

python3 make_block_shear_demo.py
ccx block_shear_demo_ccx

echo
echo "Done. Download/open block_shear_demo_ccx.frd in PrePoMax."
ls -lh block_shear_demo_ccx.* 2>/dev/null || true
