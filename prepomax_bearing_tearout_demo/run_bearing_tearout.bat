@echo off
echo Generating and running bearing/tearout demo...
py make_bearing_tearout_demo.py
ccx bearing_tearout_demo_ccx
pause
