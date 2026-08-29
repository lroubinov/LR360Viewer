@echo off
title LR 360 Viewer - WebView2 Setup
echo Installing WebView2 host support and TIFF support...
where py >nul 2>nul
if not errorlevel 1 (
  py -3 -m pip install --user --upgrade pywebview pillow
) else (
  python -m pip install --user --upgrade pywebview pillow
)
echo.
echo Done.
pause
