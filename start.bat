@echo off
rem ============================================================================
rem  Conversion Analytics - TVS Certified
rem  Quick launcher: picks an interpreter, checks dependencies, starts the app.
rem
rem  Extra arguments are passed straight through to Streamlit, e.g.
rem      start.bat --server.port 8600
rem ============================================================================
setlocal EnableExtensions EnableDelayedExpansion
title Conversion Analytics - TVS Certified
rem Always run from the folder holding this script: the app resolves the
rem bundled workbook relative to itself, and the path contains spaces.
cd /d "%~dp0"

echo.
echo  ============================================================
echo   CONVERSION ANALYTICS  -  TVS Certified
echo  ============================================================
echo   Folder : %CD%
echo.

if not exist "app.py" (
    echo  [X] app.py was not found in this folder.
    echo      Keep start.bat next to app.py.
    goto :fail
)

rem ---------------------------------------------------------------------------
rem  Interpreter: a project virtual environment wins, then the py launcher,
rem  then whatever python is on PATH.
rem ---------------------------------------------------------------------------
set "PY="
if exist ".venv\Scripts\python.exe" set "PY=.venv\Scripts\python.exe"
if not defined PY if exist "venv\Scripts\python.exe" set "PY=venv\Scripts\python.exe"
if not defined PY (
    py -3 -c "import sys" >nul 2>&1 && set "PY=py -3"
)
if not defined PY (
    python -c "import sys" >nul 2>&1 && set "PY=python"
)
if not defined PY (
    echo  [X] No working Python installation was found.
    echo      Install Python 3.10 or newer from https://www.python.org/downloads/
    echo      and tick "Add python.exe to PATH" during setup.
    goto :fail
)

for /f "delims=" %%v in ('%PY% -c "import sys;print(sys.version.split()[0])" 2^>nul') do set "PYVER=%%v"
echo   Python : !PYVER!  ^(!PY!^)

rem ---------------------------------------------------------------------------
rem  Dependencies
rem ---------------------------------------------------------------------------
%PY% -c "import streamlit, pandas, numpy, plotly, openpyxl" >nul 2>&1
if errorlevel 1 (
    echo.
    echo  [!] One or more required packages are missing
    echo      ^(streamlit, pandas, numpy, plotly, openpyxl^).
    echo.
    set "ANS="
    set /p "ANS=     Install them now from requirements.txt? [Y/N] "
    if /i not "!ANS!"=="Y" (
        echo.
        echo  Cancelled. Install them yourself with:
        echo      !PY! -m pip install -r requirements.txt
        goto :fail
    )
    echo.
    %PY% -m pip install -r requirements.txt
    if errorlevel 1 (
        echo.
        echo  [X] Installation failed. Check the messages above.
        goto :fail
    )
    echo.
)

rem ---------------------------------------------------------------------------
rem  Launch.
rem    headless=false      Streamlit opens the browser itself, so the tab always
rem                        points at the port it actually managed to bind.
rem    address=127.0.0.1   stays on this machine by default. The dashboard is
rem                        behind a sign-in screen, but it is served over plain
rem                        HTTP, so rotate the credentials in auth.py before
rem                        sharing it on the office network with
rem                        start.bat --server.address=0.0.0.0
rem ---------------------------------------------------------------------------
echo   Status : starting server, a browser tab will open shortly
echo            press Ctrl+C in this window to stop the dashboard
echo  ============================================================
echo.

%PY% -m streamlit run app.py --server.headless=false --server.address=127.0.0.1 %*
set "RC=%ERRORLEVEL%"

echo.
if not "%RC%"=="0" (
    echo  Streamlit exited with code %RC%.
    goto :fail
)
echo  Dashboard stopped.
echo.
pause
exit /b 0

:fail
echo.
pause
exit /b 1
