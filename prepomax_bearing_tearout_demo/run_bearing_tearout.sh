#!/usr/bin/env bash
set -e

python3 make_bearing_tearout_demo.py
ccx bearing_tearout_demo_ccx

echo
echo "Done. Download/open bearing_tearout_demo_ccx.frd in PrePoMax."
ls -lh bearing_tearout_demo_ccx.* 2>/dev/null || true
