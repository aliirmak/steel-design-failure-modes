@echo off
echo Generating and running block shear demo...
py make_block_shear_demo.py
ccx block_shear_demo_ccx
pause
