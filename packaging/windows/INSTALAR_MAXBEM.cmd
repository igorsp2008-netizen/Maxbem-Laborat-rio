@echo off
chcp 65001 >nul
setlocal
call "%~dp0VERIFICAR_PACOTE.cmd"
if errorlevel 1 (
  echo O pacote nao passou na verificacao. Nao altere os arquivos para ignorar este erro.
  pause
  exit /b 1
)
"%~dp0runtime\python.exe" -I -B "%~dp0install.py"
if errorlevel 1 (
  echo Instalacao nao concluida. Leia a mensagem acima.
  pause
  exit /b 1
)
pause
