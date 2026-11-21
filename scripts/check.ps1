<#
.SYNOPSIS
    Airship FinTech RL Environment - PowerShell Verification Script
    Works on Windows PowerShell 5.1 and PowerShell Core (pwsh) on Linux / macOS.
#>
$ErrorActionPreference = "Stop"
$RepoRoot = Split-Path -Parent $PSScriptRoot
Set-Location $RepoRoot

$env:PYTHONHASHSEED = "0"
$env:PYTHONPATH = "src"

# Detect Python binary
$PyBin = "python"
if (Get-Command "python" -ErrorAction SilentlyContinue) {
    $PyBin = "python"
} elseif (Get-Command "python3" -ErrorAction SilentlyContinue) {
    $PyBin = "python3"
} elseif (Get-Command "py" -ErrorAction SilentlyContinue) {
    $PyBin = "py"
}

Write-Host "`n================================================================" -ForegroundColor Cyan
Write-Host "  AIRSHIP FINTECH RL: REPRODUCIBILITY & INTEGRITY (POWERSHELL)   " -ForegroundColor Cyan
Write-Host "================================================================`n" -ForegroundColor Cyan

Write-Host "[1/3] Running pytest test suite (67 unit & contract tests)..." -ForegroundColor Magenta
& $PyBin -m pytest tests -v
if ($LASTEXITCODE -ne 0) {
    Write-Host "[FAIL] Pytest tests failed." -ForegroundColor Red
    exit $LASTEXITCODE
}

Write-Host "`n[2/3] Synthesizing 20 benchmark episodes..." -ForegroundColor Magenta
& $PyBin scripts/make_episodes.py
if ($LASTEXITCODE -ne 0) {
    Write-Host "[FAIL] Episode synthesis failed." -ForegroundColor Red
    exit $LASTEXITCODE
}

Write-Host "`n[3/3] Benchmarking 4 baseline policies on 20 episodes..." -ForegroundColor Green
& $PyBin scripts/run_policies.py
if ($LASTEXITCODE -ne 0) {
    Write-Host "[FAIL] Policy benchmark failed." -ForegroundColor Red
    exit $LASTEXITCODE
}

Write-Host "`n================================================================" -ForegroundColor Green
Write-Host "  [OK] ALL VERIFICATION CHECKS PASSED PERFECTLY (100% SUCCESS)    " -ForegroundColor Green
Write-Host "================================================================`n" -ForegroundColor Green
