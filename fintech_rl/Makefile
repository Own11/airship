.PHONY: check test demo generate episodes clean docker-build docker-run help

help:
	@echo "Fintech RL Environment Commands:"
	@echo "  make check        - Run full verification pipeline (pytest + generate + run policies)"
	@echo "  make test         - Run 62 unit and contract tests via pytest"
	@echo "  make demo         - Run interactive step-by-step audit episode demo"
	@echo "  make episodes     - Re-generate 10 train and 10 dev episodes"
	@echo "  make docker-build - Build clean Docker image (python:3.11-slim)"
	@echo "  make docker-run   - Run check pipeline in Docker with --network none"
	@echo "  make clean        - Remove Python bytecode and test cache files"

check:
	@./scripts/check.sh

test:
	@PYTHONHASHSEED=0 python3 -m pytest tests -v

demo:
	@PYTHONPATH=src python3 scripts/demo.py

episodes:
	@PYTHONPATH=src python3 scripts/make_episodes.py

clean:
	@find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	@find . -type d -name ".pytest_cache" -exec rm -rf {} + 2>/dev/null || true
	@find . -type f -name "*.pyc" -delete 2>/dev/null || true

docker-build:
	docker build -t fintech-rl:latest .

docker-run:
	docker run --rm --network none fintech-rl:latest ./scripts/check.sh
