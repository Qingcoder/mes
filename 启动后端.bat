@echo off
chcp 65001 >nul
cd /d "%~dp0"
title Daimon MES - Backend

echo ==========================================
echo   Daimon MES Backend  :8007
echo ==========================================
echo.

REM ---- Step 1: locate python.exe by absolute path (NO PATH dependency) ----
set "PY="
if exist "%~dp0backend\.venv\Scripts\python.exe" set "PY=%~dp0backend\.venv\Scripts\python.exe"
if not defined PY if exist "%LOCALAPPDATA%\Programs\Python\Python315\python.exe" set "PY=%LOCALAPPDATA%\Programs\Python\Python315\python.exe"
if not defined PY if exist "%LOCALAPPDATA%\Programs\Python\Python313\python.exe" set "PY=%LOCALAPPDATA%\Programs\Python\Python313\python.exe"
if not defined PY if exist "%LOCALAPPDATA%\Programs\Python\Python312\python.exe" set "PY=%LOCALAPPDATA%\Programs\Python\Python312\python.exe"
if not defined PY if exist "%LOCALAPPDATA%\Programs\Python\Python311\python.exe" set "PY=%LOCALAPPDATA%\Programs\Python\Python311\python.exe"
if not defined PY if exist "C:\Python315\python.exe" set "PY=C:\Python315\python.exe"
if not defined PY if exist "C:\Python313\python.exe" set "PY=C:\Python313\python.exe"
if not defined PY if exist "C:\Python312\python.exe" set "PY=C:\Python312\python.exe"
if not defined PY if exist "C:\Python311\python.exe" set "PY=C:\Python311\python.exe"
if not defined PY (
  echo [ERROR] Python 3.11+ not found.
  echo Tried: project .venv, user Python315/313/312/311, C:\Python3xx
  echo Install Python 3.11+ or tell me the exact python.exe path to hardcode.
  pause
  exit /b 1
)
echo [OK] Python: %PY%
"%PY%" --version

REM ---- Step 2: create venv on first run (absolute path, no PATH needed) ----
if not exist "%~dp0backend\.venv\Scripts\python.exe" (
  echo.
  echo [1/4] First run: creating virtual environment ...
  "%PY%" -m venv "%~dp0backend\.venv" || (echo Failed to create venv & pause & exit /b 1)
)
set "VPY=%~dp0backend\.venv\Scripts\python.exe"

REM ---- Step 3: install dependencies (venv has its own pip) ----
echo [2/4] Checking dependencies ...
"%VPY%" -m pip install -q --disable-pip-version-check -r "%~dp0backend\requirements.txt" || (echo Dependency install failed, check network & pause & exit /b 1)
echo [OK] Dependencies ready

REM ---- Step 4: ensure frontend dist exists (auto-build if missing) ----
if not exist "%~dp0frontend\dist\index.html" (
  echo [3/4] Frontend build missing, building ...
  set "NODE="
  if exist "C:\Program Files\nodejs\node.exe" set "NODE=C:\Program Files\nodejs\node.exe"
  if not defined NODE if exist "%ProgramFiles(x86)%\nodejs\node.exe" set "NODE=%ProgramFiles(x86)%\nodejs\node.exe"
  if not defined NODE (
    echo [ERROR] Node.js not found. dist is required for login page.
    pause
    exit /b 1
  )
  set "NPM="
  if exist "C:\Program Files\nodejs\npm.cmd" set "NPM=C:\Program Files\nodejs\npm.cmd"
  if not defined NPM if exist "%ProgramFiles(x86)%\nodejs\npm.cmd" set "NPM=%ProgramFiles(x86)%\nodejs\npm.cmd"
  pushd "%~dp0frontend"
  if not exist "node_modules" ( "%NPM%" install --no-audit --no-fund --force )
  "%NODE%" "node_modules\vite\bin\vite.js" build
  popd
  if not exist "%~dp0frontend\dist\index.html" (echo [ERROR] Frontend build failed & pause & exit /b 1)
  echo [OK] Frontend built
) else (
  echo [3/4] Frontend dist ready
)

REM ---- Step 5: start server ----
echo [4/4] Starting backend on :8007 ...
echo.
set "LANIP="
for /f "delims=" %%i in ('powershell -NoProfile -Command "(Get-NetIPAddress -AddressFamily IPv4 | Where-Object {$_.IPAddress -notlike '127.*' -and $_.IPAddress -notlike '169.254.*'} | Select-Object -First 1).IPAddress"') do set "LANIP=%%i"
echo   PC login   : http://127.0.0.1:8007/login
if defined LANIP (echo   Phone login: http://%LANIP%:8007/login) else (echo   Phone login: use PC LAN IP :8007/login)
echo.
cd /d "%~dp0backend"
"%VPY%" -m uvicorn app.main:app --host 0.0.0.0 --port 8007
pause
