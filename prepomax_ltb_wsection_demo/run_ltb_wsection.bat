@echo off
echo Generating and running W-section LTB demo...
py make_ltb_wsection_demo.py
ccx ltb_wsection_demo_ccx
pause
