@echo off
set PYTHONPATH=src
set PYTHONHASHSEED=0
if "%1"=="demo" python scripts/demo.py
if "%1"=="play" python scripts/cli.py play train_ep_03
if "%1"=="benchmark" python scripts/run_policies.py
if "%1"=="evaluate" python scripts/run_policies.py
if "%1"=="check" python -m pytest tests -v && python scripts/make_episodes.py && python scripts/run_policies.py