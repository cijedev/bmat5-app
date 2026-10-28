@echo off
REM BMW interactive menu (Python). Double-click this file in Explorer.
cd /d "%~dp0"
py -3 bmat_menu.py 2>nul || python bmat_menu.py
pause
