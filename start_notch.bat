@echo off
cd /d "%~dp0"
if exist "spfnotch.exe" (
    start "" "spfnotch.exe"
) else (
    start "" pythonw app/main.py
)
exit
