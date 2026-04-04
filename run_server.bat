@echo off
setlocal EnableExtensions
cd /d "%~dp0"

if exist ".venv\Scripts\activate.bat" (
    call ".venv\Scripts\activate.bat"
) else (
    echo [run_server] No .venv found in this folder.
    echo   Create it:  python -m venv .venv
    echo   Then:       .\.venv\Scripts\activate
    echo                 pip install -r requirements.txt
    echo.
    echo Trying system Python anyway...
    echo.
)

echo Social Safety prototype
echo   API + UI:  http://127.0.0.1:8080
echo   Chat:      http://127.0.0.1:8080/index.html
echo   Moderator: http://127.0.0.1:8080/moderator.html
echo.
echo Port 8080 avoids Windows issues with port 8000.
echo Stop the server: Ctrl+C
echo.

python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8080
set "EC=%ERRORLEVEL%"
if not "%EC%"=="0" (
    echo.
    echo Server stopped with error code %EC%.
    pause
)
endlocal & exit /b %EC%
