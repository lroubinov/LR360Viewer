@echo off
setlocal
set "LOG=%TEMP%\LR360Viewer.log"

echo ================================================== > "%LOG%"
echo LR360Viewer launcher started: %DATE% %TIME% >> "%LOG%"
echo Image: %~1 >> "%LOG%"

if "%~1"=="" exit /b 2
if not exist "%~1" exit /b 3

if exist "%~dp0LR360Viewer.exe" (
  echo Starting packaged LR360Viewer.exe >> "%LOG%"
  start "" "%~dp0LR360Viewer.exe" "%~1"
  exit /b 0
)

rem Developer fallback only.
where py >nul 2>nul
if not errorlevel 1 (
  py -3 -c "import webview; import PIL" >nul 2>nul
  if errorlevel 1 py -3 -m pip install --user --quiet pywebview pillow
  start "" /b pyw -3 "%~dp0server.py" "%~1"
  exit /b 0
)

where python >nul 2>nul
if not errorlevel 1 (
  python -c "import webview; import PIL" >nul 2>nul
  if errorlevel 1 python -m pip install --user --quiet pywebview pillow
  start "" /b pythonw "%~dp0server.py" "%~1"
  exit /b 0
)

echo ERROR: LR360Viewer.exe missing and Python was not found. >> "%LOG%"
start "" notepad.exe "%LOG%"
exit /b 10
