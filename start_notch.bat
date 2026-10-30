@echo off
cd /d "%~dp0"
where pythonw >nul 2>nul
if %errorlevel% equ 0 (
    start "" pythonw app/main.py
) else if exist "spfnotch.exe" (
    start "" "spfnotch.exe"
)
exit
