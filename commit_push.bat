@echo off
setlocal EnableExtensions
cd /d "%~dp0"

where git >nul 2>&1
if errorlevel 1 (
  echo Git is not in PATH. Install Git for Windows or use Git Bash.
  pause
  exit /b 1
)

if not exist ".git\" (
  echo No .git folder here. Run: git init
  pause
  exit /b 1
)

echo.
echo Staging all changes ^(git add -A^)...
git add -A
if errorlevel 1 (
  echo git add failed.
  pause
  exit /b 1
)

git diff --cached --quiet
if errorlevel 1 goto CommitAndPush

echo No changes to commit ^(working tree clean after staging^).
echo.
set /p PUSH_ANYWAY=Push unpushed commits anyway? [y/N]: 
if /i "%PUSH_ANYWAY%"=="y" goto DoPush
echo Done.
pause
exit /b 0

:CommitAndPush
echo.
echo Tip: avoid double-quote ^("^) characters in the message; they can break this script.
set /p COMMIT_MSG=Commit message: 
if not defined COMMIT_MSG (
  echo Aborted: empty commit message.
  pause
  exit /b 1
)

git commit -m "%COMMIT_MSG%"
if errorlevel 1 (
  echo git commit failed ^(see message above^).
  pause
  exit /b 1
)

:DoPush
echo.
echo Pushing...
git push
set "EC=%ERRORLEVEL%"
if not "%EC%"=="0" (
  echo.
  echo Push failed. If the branch has no upstream yet, run once:
  echo   git push -u origin main
  pause
  exit /b %EC%
)

echo.
echo Done.
pause
endlocal & exit /b 0
