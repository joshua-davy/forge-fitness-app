@echo off
setlocal

set "ROOT=%~dp0"
set "BACKEND=%ROOT%backend"
set "WEB=%ROOT%web"
set "API_URL=http://127.0.0.1:8001"
set "WEB_URL=http://127.0.0.1:5173"
set "PYTHON_EXE=C:\Users\joshu\AppData\Local\Programs\Python\Python312\python.exe"
set "PYTHON_ARGS="

title Forge Launcher
echo.
echo ========================================
echo   Forge local launcher
echo ========================================
echo.

if not exist "%PYTHON_EXE%" (
  where py >nul 2>nul
  if errorlevel 1 (
    echo Python was not found. Install Python 3.12 or add it to PATH.
    pause
    exit /b 1
  )
  set "PYTHON_EXE=py"
  set "PYTHON_ARGS=-3"
)

where npm.cmd >nul 2>nul
if errorlevel 1 (
  echo npm was not found. Install Node.js LTS or add it to PATH.
  pause
  exit /b 1
)

echo Checking backend dependencies...
pushd "%BACKEND%" >nul
"%PYTHON_EXE%" %PYTHON_ARGS% -c "import fastapi, uvicorn, garminconnect, sqlalchemy" >nul 2>nul
if errorlevel 1 (
  echo Installing backend dependencies...
  "%PYTHON_EXE%" %PYTHON_ARGS% -m pip install -r requirements.txt
  if errorlevel 1 (
    echo Backend dependency install failed.
    popd >nul
    pause
    exit /b 1
  )
)
popd >nul

if not exist "%WEB%\node_modules" (
  echo Installing frontend dependencies...
  pushd "%WEB%" >nul
  call npm.cmd install
  if errorlevel 1 (
    echo Frontend dependency install failed.
    popd >nul
    pause
    exit /b 1
  )
  popd >nul
)

if /I "%~1"=="--check" (
  echo Launcher check passed.
  exit /b 0
)

echo.
echo Starting Forge backend on %API_URL% ...
start "Forge Backend" powershell -NoExit -ExecutionPolicy Bypass -Command "Set-Location -LiteralPath '%BACKEND%'; $env:PYTHONUTF8='1'; & '%PYTHON_EXE%' %PYTHON_ARGS% -m uvicorn app.main:app --host 127.0.0.1 --port 8001"

echo Starting Forge frontend on %WEB_URL% ...
start "Forge Frontend" powershell -NoExit -ExecutionPolicy Bypass -Command "Set-Location -LiteralPath '%WEB%'; $env:VITE_API_URL='%API_URL%'; npm.cmd run dev -- --host 127.0.0.1 --port 5173"

echo.
echo Opening Forge in your browser...
timeout /t 5 /nobreak >nul
start "" "%WEB_URL%"

echo.
echo Forge is starting.
echo Keep the Backend and Frontend windows open while using the app.
echo Close those windows to stop Forge.
echo.
pause
