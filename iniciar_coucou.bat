@echo off
title Coucou Launcher
cd /d "%~dp0"

echo [1/2] Verificando servidor de voz Caf (Python)...
netstat -ano | findstr :8000 >nul
if %errorlevel% neq 0 (
    echo Iniciando backend en segundo plano...
    cd backend
    start /b python -m uvicorn server:app --host 127.0.0.1 --port 8000
    cd ..
    timeout /t 2 /nobreak >nul
) else (
    echo Backend ya activo en el puerto 8000.
)

echo [2/2] Lanzando Coucou...
if exist "windows\src-tauri\target\release\Coucou.exe" (
    start "" "windows\src-tauri\target\release\Coucou.exe"
) else (
    cd windows
    npm run tauri dev
)
