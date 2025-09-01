@echo off
REM Use the venv Python directly to avoid activation/reload path issues
REM Determine script directory (web folder)
set SCRIPT_DIR=%~dp0
cd /d "%SCRIPT_DIR%"

REM Allow overriding the python executable via environment variable VENV_PY
if defined VENV_PY goto :have_python

REM Common venv locations (relative to this script)
set CAND1=%~dp0..\..\venv\Scripts\python.exe
set CAND2=%~dp0..\.venv\Scripts\python.exe
set CAND3=%~dp0..\venv\Scripts\python.exe

if exist "%CAND1%" (
	set VENV_PY=%CAND1%
	goto :have_python
)
if exist "%CAND2%" (
	set VENV_PY=%CAND2%
	goto :have_python
)
if exist "%CAND3%" (
	set VENV_PY=%CAND3%
	goto :have_python
)

REM Fallback to system python
set VENV_PY=python

:have_python
echo Using Python executable: %VENV_PY%

REM Start the FastAPI server using the selected python and uvicorn module.
REM --reload-dir ensures the reloader watches this folder for changes.
"%VENV_PY%" -m uvicorn main:app --host 0.0.0.0 --port 8000 --reload --reload-dir .

REM If the server stops, pause so the window stays open to see logs
pause
