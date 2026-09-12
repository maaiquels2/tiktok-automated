@echo off
setlocal
set "FABRICA_ROOT=%~dp0"
echo Encerrando o servidor da Fabrica TikTok...
powershell -NoProfile -ExecutionPolicy Bypass -Command "$root=$env:FABRICA_ROOT.TrimEnd('\'); Get-CimInstance Win32_Process -Filter \"Name='pythonw.exe'\" | Where-Object { $_.CommandLine -and $_.CommandLine -like ('*'+$root+'*') } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }"
timeout /t 1 /nobreak >nul
echo Iniciando a Fabrica TikTok...
start "" wscript.exe "%~dp0iniciar.vbs"
endlocal
