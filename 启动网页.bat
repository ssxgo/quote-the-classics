@echo off
setlocal EnableExtensions
pushd "%~dp0web" || exit /b 1

if not defined YANJING_WEB_PORT set "YANJING_WEB_PORT=8000"
set "YANJING_READER_URL=http://127.0.0.1:%YANJING_WEB_PORT%"
set "YANJING_WEB_DEV="

call :check_reader
if not errorlevel 1 (
    echo Reader is already running at %YANJING_READER_URL%
    if /i not "%~1"=="--no-browser" start "" "%YANJING_READER_URL%"
    popd
    exit /b 0
)

where uv >nul 2>&1 || set "PATH=%LOCALAPPDATA%\Programs\uv;%PATH%"
where uv >nul 2>&1 || goto missing_uv
where node >nul 2>&1 && where pnpm >nul 2>&1 && goto setup
for /f "delims=" %%I in ('powershell.exe -NoProfile -Command "$packages = @(Get-AppxPackage -Name OpenAI.CodexPrimaryRuntime*); if ($packages.Count) { $packages[0].InstallLocation }"') do set "YANJING_CODEX_RUNTIME=%%I"
if defined YANJING_CODEX_RUNTIME set "PATH=%YANJING_CODEX_RUNTIME%\dependencies\node\bin;%YANJING_CODEX_RUNTIME%\dependencies\bin\fallback;%PATH%"
where node >nul 2>&1 || goto missing_frontend
where pnpm >nul 2>&1 || goto missing_frontend

:setup
set "YANJING_WEB_PYTHON=%USERPROFILE%\Documents\Codex\python-ml\.venv\Scripts\python.exe"
if not exist "%YANJING_WEB_PYTHON%" set "YANJING_WEB_PYTHON=3.12"
uv sync --locked --python "%YANJING_WEB_PYTHON%"
if errorlevel 1 goto failed
call pnpm install --frozen-lockfile
if errorlevel 1 goto failed
call pnpm build
if errorlevel 1 goto failed

echo Starting the reader at %YANJING_READER_URL%
echo Press Ctrl+C in this window to stop the server.
if /i not "%~1"=="--no-browser" start "" /b powershell.exe -NoProfile -Command "for ($i = 0; $i -lt 30; $i++) { try { $books = Invoke-RestMethod -Uri ($env:YANJING_READER_URL + '/api/books') -TimeoutSec 2; if ($books[0].id -eq 'analects' -and $books[1].id -eq 'tao_te_ching') { Start-Process $env:YANJING_READER_URL; exit } } catch {}; Start-Sleep -Milliseconds 500 }"
uv run --locked uvicorn server:app --host 127.0.0.1 --port %YANJING_WEB_PORT%
if errorlevel 1 goto failed
popd
exit /b 0

:check_reader
powershell.exe -NoProfile -Command "try { $books = Invoke-RestMethod -Uri ($env:YANJING_READER_URL + '/api/books') -TimeoutSec 2; if ($books[0].id -eq 'analects' -and $books[1].id -eq 'tao_te_ching') { exit 0 } } catch {}; exit 1"
exit /b %errorlevel%

:missing_uv
echo uv was not found. Install uv or add it to PATH.
goto failed

:missing_frontend
echo Node.js and pnpm are required. Install them or add them to PATH.

:failed
echo The reader could not start. See the error above.
popd
if /i not "%~1"=="--no-browser" pause
exit /b 1
