#!/usr/bin/env bash
set -e

python make_a992_web_coupon.py
ccx a992_web_coupon_ccx

echo
echo "Done. Download these files and open the .frd in PrePoMax:"
ls -lh a992_web_coupon_ccx.inp a992_web_coupon_ccx.frd a992_web_coupon_ccx.dat 2>/dev/null || true