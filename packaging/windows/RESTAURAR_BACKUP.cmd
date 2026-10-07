@echo off
chcp 65001 >nul
setlocal
call "%~dp0VERIFICAR_PACOTE.cmd"
if errorlevel 1 (
  echo O pacote nao passou na verificacao. Nao altere os arquivos para ignorar este erro.
  pause
  exit /b 1
)
if "%~1"=="" (
  echo Feche o servidor. Arraste um backup .sqlite3 sobre este arquivo.
  pause
  exit /b 1
)
choice /C SN /M "Restaurar backup preservando a copia anterior"
if errorlevel 2 exit /b 0
"%~dp0runtime\python.exe" -I -B "%~dp0server.py" --restore "%~1"
pause
