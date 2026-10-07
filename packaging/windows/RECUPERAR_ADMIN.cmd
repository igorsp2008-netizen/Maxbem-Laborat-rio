@echo off
chcp 65001 >nul
setlocal
call "%~dp0VERIFICAR_PACOTE.cmd"
if errorlevel 1 (
  echo O pacote nao passou na verificacao. Nao altere os arquivos para ignorar este erro.
  pause
  exit /b 1
)
echo Feche o servidor antes de recuperar a conta.
"%~dp0runtime\python.exe" -I -B "%~dp0server.py" --reset-admin
pause
