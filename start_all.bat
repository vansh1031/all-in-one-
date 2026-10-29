@echo off
rem Starts both apps, each in its own window, and opens them in the browser.
rem Close a window to stop that app.
start "Hazardous Zone Detector" "%~dp0scripts\start_hazard_zone.bat"
start "Predictive Maintenance" "%~dp0scripts\start_predictive_maintenance.bat"
