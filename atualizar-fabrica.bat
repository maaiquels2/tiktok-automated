@echo off
setlocal
cd /d "%~dp0"
echo Baixando a versao mais nova da Fabrica TikTok...
git pull
if errorlevel 1 (
  echo.
  echo Nao foi possivel baixar a versao nova. Confira a internet e tente de novo.
  pause
  exit /b 1
)
echo Instalando e montando a tela nova...
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0instalar.ps1"
if errorlevel 1 (
  echo.
  echo A instalacao falhou. Mande um print desta janela.
  pause
  exit /b 1
)
call "%~dp0reiniciar-fabrica.bat"
echo.
echo Pronto! A Fabrica TikTok foi atualizada e reiniciada.
pause
endlocal
