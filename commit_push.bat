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
set "GIT_BRANCH="
for /f "delims=" %%b in ('git rev-parse --abbrev-ref HEAD 2^>nul') do set "GIT_BRANCH=%%b"
if not defined GIT_BRANCH (
  echo Could not detect branch name. Run: git push -u origin main
  pause
  exit /b 1
)
git push -u origin "%GIT_BRANCH%"
set "EC=%ERRORLEVEL%"
if not "%EC%"=="0" (
  echo.
  echo Push failed. Check: git remote -v
  echo If there is no origin: git remote add origin ^<your-repo-url^>
  pause
  exit /b %EC%
)

echo.
echo Done.
pause
endlocal & exit /b 0
