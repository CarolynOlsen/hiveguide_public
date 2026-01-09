@echo off
setlocal enableextensions enabledelayedexpansion
REM -------------------------------------------------
#REM launch_app.bat – start the Hive‑Guide app
REM Handles both local dev (FastAPI + React) and Docker container.
REM -------------------------------------------------

REM ==== CONFIGURATION ==================================================
set ROOT=%~dp0..\..
pushd "%ROOT%"
set IMAGE_NAME=hivescribe
set CONTAINER_NAME=hivescribe_app
set HOST_PORT=8000
set APP_ENTRY=main
REM =====================================================================

REM ---- Helper to kill any running uvicorn process (local dev) ----
for /f "tokens=2" %%a in ('tasklist ^| findstr uvicorn') do taskkill /PID %%a /F

REM ---- Ensure frontend deps (for React Native Web) ----
pushd web-rn
call npm install --legacy-peer-deps --no-fund --no-audit
if %ERRORLEVEL% NEQ 0 (
    echo *** ERROR: npm install failed ***
    popd
    exit /b 1
)

REM ---- Build React Native Web frontend ----
call npm run build
if %ERRORLEVEL% NEQ 0 (
    echo *** ERROR: frontend build failed ***
    popd
    exit /b 1
)
popd

REM ---- Clean and copy build output to static/ ----
if exist backend\static\assets rmdir /S /Q backend\static\assets
if exist backend\static\index.html del /F /Q backend\static\index.html
xcopy /E /I /Y "%ROOT%\web-rn\dist\*" "%ROOT%\backend\static\" >nul
echo Copied React Native Web build to static/.

REM ---- Verify key UI strings present in built bundle ----
for /f "delims=" %%F in ('dir /b "%ROOT%\backend\static\assets\index-*.js" 2^>nul') do set BUNDLE=%ROOT%\backend\static\assets\%%F
if not defined BUNDLE echo WARNING: bundle not found in backend\static\assets & goto after_copy
findstr /I /C:"Ask a beekeeping question" "%BUNDLE%" >nul && echo Verified: chat placeholder present.
findstr /I /C:"Dictate." "%BUNDLE%" >nul && echo Verified: mic tooltip present.
:after_copy

REM ---- Detect Docker ----
where docker >nul 2>&1
if %ERRORLEVEL% EQU 0 (
    echo Docker CLI detected – checking daemon...
    docker info >nul 2>&1
    if %ERRORLEVEL% EQU 0 (
        echo Docker daemon is running – will run the app inside a container.

        REM Always (re)build Docker image to ensure latest static assets
        echo Building Docker image "%IMAGE_NAME%"...
        docker build -t %IMAGE_NAME% .
        if %ERRORLEVEL% NEQ 0 (
            echo *** ERROR: Docker build failed ***
            exit /b 1
        )

        REM Remove any previous container with same name
        docker ps -a --filter "name=%CONTAINER_NAME%" --format "{{.ID}}" >nul
        for /f %%i in ('docker ps -a --filter "name=%CONTAINER_NAME%" --format "{{.ID}}"') do set CONTAINER_ID=%%i
        if defined CONTAINER_ID (
            echo Removing old container "%CONTAINER_NAME%"...
            docker rm -f %CONTAINER_NAME% >nul 2>&1
        )

        REM Run container
        echo Starting container "%CONTAINER_NAME%" on port %HOST_PORT%...
        docker run -d ^
            --name %CONTAINER_NAME% ^
            -p %HOST_PORT%:8000 ^
            -e TESSERACT_PATH=/usr/bin/tesseract ^
            %IMAGE_NAME%
        if %ERRORLEVEL% NEQ 0 (
            echo *** ERROR: Docker run failed ***
            exit /b 1
        )
        echo *** SUCCESS: Container is running ***
        echo Access the app at http://localhost:%HOST_PORT%
        goto :eof
    ) else (
        echo Docker CLI found but daemon is not running. Falling back to local dev.
    )
)

REM ---- Fallback to local dev (no Docker) ----
REM Activate virtual environment if present
if exist "%ROOT%\.venv\Scripts\activate.bat" (
    call "%ROOT%\.venv\Scripts\activate.bat"
)

REM Start FastAPI server
start uvicorn backend.%APP_ENTRY%:app --reload --port %HOST_PORT%

echo App launched locally! Open http://127.0.0.1:%HOST_PORT%
pause
popd
endlocal