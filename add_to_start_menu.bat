@echo off
cd /d "%~dp0"
powershell -NoProfile -ExecutionPolicy Bypass -Command "$WshShell = New-Object -ComObject WScript.Shell; $Shortcut = $WshShell.CreateShortcut([System.IO.Path]::Combine($env:APPDATA, 'Microsoft\Windows\Start Menu\Programs\spfnotch.lnk')); $Shortcut.TargetPath = (Join-Path '%~dp0' 'spfnotch.exe'); $Shortcut.WorkingDirectory = '%~dp0'; $Shortcut.IconLocation = (Join-Path '%~dp0' 'app\assets\icon.ico') + ', 0'; $Shortcut.Description = 'spfnotch - Spotify Dynamic Notch'; $Shortcut.Save()"
echo.
echo ========================================================
echo  spfnotch berhasil didaftarkan ke Start Menu Windows!
echo ========================================================
echo Sekarang kamu bisa mencari 'spfnotch' di Windows Search.
echo.
pause
