@echo off
setlocal
cd /d "%~dp0\.."

set PYTHONHASHSEED=0

rem Detect working Python binary: python, python3, or py
where python >nul 2>nul
if %ERRORLEVEL% equ 0 (
    set "PY_BIN=python"
    goto :run
)
where python3 >nul 2>nul
if %ERRORLEVEL% equ 0 (
    set "PY_BIN=python3"
    goto :run
)
where py >nul 2>nul
if %ERRORLEVEL% equ 0 (
    set "PY_BIN=py"
    goto :run
)
echo [ERROR] Python not found in PATH.
exit /b 1

:run
echo.
echo ================================================================
echo   AIRSHIP FINTECH RL: REPRODUCIBILITY ^& INTEGRITY (WINDOWS)
echo ================================================================
echo.
echo [1/3] Running pytest test suite (67 unit ^& contract tests)...
%PY_BIN% -m pytest tests -v
if %ERRORLEVEL% neq 0 (
    echo [FAIL] Pytest tests failed.
    exit /b %ERRORLEVEL%
)

echo.
echo [2/3] Synthesizing 20 benchmark episodes...
set "PYTHONPATH=src"
%PY_BIN% scripts\make_episodes.py
if %ERRORLEVEL% neq 0 (
    echo [FAIL] Episode synthesis failed.
    exit /b %ERRORLEVEL%
)

echo.
echo [3/3] Benchmarking 4 baseline policies on 20 episodes...
%PY_BIN% scripts\run_policies.py
if %ERRORLEVEL% neq 0 (
    echo [FAIL] Policy benchmark failed.
    exit /b %ERRORLEVEL%
)

echo.
echo ================================================================
echo   [OK] ALL VERIFICATION CHECKS PASSED PERFECTLY (100%% SUCCESS)
echo ================================================================
echo.
endlocal
