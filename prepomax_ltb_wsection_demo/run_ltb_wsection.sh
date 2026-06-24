#!/usr/bin/env bash
set -e

python3 make_ltb_wsection_demo.py
ccx ltb_wsection_demo_ccx

echo
echo "Done. Download/open ltb_wsection_demo_ccx.frd in PrePoMax."
ls -lh ltb_wsection_demo_ccx.* 2>/dev/null || true
