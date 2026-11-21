.PHONY: check test demo benchmark generate episodes inspect play cli clean docker-build docker-run help

# Terminal Colors for Makefile
CYAN   := \033[38;5;45m
GREEN  := \033[38;5;48m
YELLOW := \033[38;5;214m
GRAY   := \033[38;5;244m
BOLD   := \033[1m
RESET  := \033[0m

# Cross-platform Python detection (macOS, Linux, Windows)
PYTHON ?= $(shell command -v python3 2>/dev/null || command -v python 2>/dev/null || echo python3)

help:
	@echo ""
	@echo "$(CYAN)$(BOLD)Airship FinTech RL Environment Commands:$(RESET)"
	@echo "  $(GREEN)make check$(RESET)        $(GRAY)- Run full verification pipeline (pytest + generate + benchmark)$(RESET)"
	@echo "  $(GREEN)make test$(RESET)         $(GRAY)- Run 67 unit and contract tests via pytest$(RESET)"
	@echo "  $(GREEN)make demo$(RESET)         $(GRAY)- Run interactive step-by-step audit walkthrough$(RESET)"
	@echo "  $(GREEN)make benchmark$(RESET)    $(GRAY)- Benchmark 4 policies across all 20 episodes$(RESET)"
	@echo "  $(GREEN)make episodes$(RESET)     $(GRAY)- Re-generate 10 train and 10 dev episodes$(RESET)"
	@echo "  $(GREEN)make inspect$(RESET)      $(GRAY)- Inspect sample episode ledger records and manifest$(RESET)"
	@echo "  $(GREEN)make play$(RESET)         $(GRAY)- Launch Human Auditor interactive terminal session$(RESET)"
	@echo "  $(GREEN)make cli$(RESET)          $(GRAY)- View Airship CLI command menu$(RESET)"
	@echo "  $(GREEN)make docker-build$(RESET) $(GRAY)- Build clean Docker image (python:3.11-slim)$(RESET)"
	@echo "  $(GREEN)make docker-run$(RESET)   $(GRAY)- Run check pipeline in Docker with --network none$(RESET)"
	@echo "  $(GREEN)make clean$(RESET)        $(GRAY)- Remove Python bytecode and test cache files$(RESET)"
	@echo ""

check:
	@./scripts/check.sh

test:
	@PYTHONHASHSEED=0 $(PYTHON) -m pytest tests -v

demo:
	@PYTHONPATH=src $(PYTHON) scripts/demo.py

benchmark:
	@PYTHONPATH=src $(PYTHON) scripts/run_policies.py

episodes:
	@PYTHONPATH=src $(PYTHON) scripts/make_episodes.py

inspect:
	@PYTHONPATH=src $(PYTHON) scripts/cli.py inspect train_ep_03 --table ledger --limit 10

play:
	@PYTHONPATH=src $(PYTHON) scripts/cli.py play train_ep_03

cli:
	@PYTHONPATH=src $(PYTHON) scripts/cli.py

clean:
	@$(PYTHON) -c "import pathlib, shutil; [shutil.rmtree(p) for p in pathlib.Path('.').rglob('__pycache__')]; [shutil.rmtree(p) for p in pathlib.Path('.').rglob('.pytest_cache')]; [p.unlink() for p in pathlib.Path('.').rglob('*.pyc')]"

docker-build:
	docker build -t airship:latest .

docker-run:
	docker run --rm --network none airship:latest ./scripts/check.sh
