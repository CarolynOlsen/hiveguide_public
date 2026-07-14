@echo off
REM -------------------------------------------------
REM stop_app.bat – stop the Hive‑Guide app
REM Handles both Docker container and local uvicorn process
REM -------------------------------------------------

REM ==== CONFIGURATION ==================================================
set CONTAINER_NAME=hiveguide_app
set HOST_PORT=8000
REM =====================================================================

REM ---- Detect Docker -------------------------------------------------
where docker >nul 2>&1
if %ERRORLEVEL% EQU 0 (
    echo Docker detected – stopping Docker container...

    :: Stop and remove the container (if it exists)
    docker rm -f %CONTAINER_NAME% >nul 2>&1
    if %ERRORLEVEL% EQU 0 (
        echo Container %CONTAINER_NAME% stopped and removed.
    ) else (
        echo No running container %CONTAINER_NAME% found.
    )
) else (
    echo Docker not found – falling back to local dev cleanup.

    :: Kill any running uvicorn process
    for /f "tokens=2" %%a in ('tasklist ^| findstr uvicorn') do (
        echo Killing uvicorn process (PID %%a)...
        taskkill /PID %%a /F >nul 2>&1
    )
    echo Local uvicorn server stopped (if it was running).
)

echo Done. Press any key to close…
pause
