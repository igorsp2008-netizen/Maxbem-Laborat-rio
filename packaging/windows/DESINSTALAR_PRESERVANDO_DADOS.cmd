@echo off
chcp 65001 >nul
setlocal
call "%~dp0VERIFICAR_PACOTE.cmd"
if errorlevel 1 (
  echo O pacote nao passou na verificacao. Nao altere os arquivos para ignorar este erro.
  pause
  exit /b 1
)
echo Feche o servidor. Banco e backups serao preservados.
choice /C SN /M "Remover apenas o aplicativo seguro"
if errorlevel 2 exit /b 0
"%~dp0runtime\python.exe" -I -B "%~dp0uninstall.py"
if errorlevel 1 (
  pause
  exit /b 1
)
(
  if exist "%LOCALAPPDATA%\MaxbemLaboratorio\AppSeguro-anterior" rmdir /S /Q "%LOCALAPPDATA%\MaxbemLaboratorio\AppSeguro-anterior"
  if exist "%LOCALAPPDATA%\MaxbemLaboratorio\AppSeguro" rmdir /S /Q "%LOCALAPPDATA%\MaxbemLaboratorio\AppSeguro"
  echo Banco e backups preservados. Verifique acima eventuais arquivos que nao puderam ser removidos.
  pause
  exit /b 0
)
