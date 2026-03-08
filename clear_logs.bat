@echo off
setlocal

set "LOG=%LOCALAPPDATA%\hel_zapret_ui\app.log"

if exist "%LOG%" (
  del /f /q "%LOG%" >nul 2>nul
)

endlocal