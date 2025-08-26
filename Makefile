.PHONY: dev test lint type sim-smoke train accept replay bench client e2e clean help

help: ## Show this help message
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'

dev: ## Install toolchain
	pip install -U pip && pip install -e .[dev]
	npm --prefix client ci

lint: ## Run linters
	ruff check . && black --check . && cd client && npx eslint "src/**/*.{ts,tsx}"

type: ## Run type checkers
	mypy sim && cd client && npx tsc --noEmit

test: ## Run unit tests
	pytest -q --maxfail=1

sim-smoke: ## 150 agents @ 60Hz for 60s headless
	python -m sim.cli.run --level W1-1 --agents 150 --ticks 3600 --headless --seed 123 --record out/smoke.jsonl

train: ## One-epoch PPO-lite sanity
	python -m sim.cli.train --level W1-1 --epochs 1 --seed 123 --wandb $(WANDB)

accept: ## Full acceptance suite
	python -m tests.acceptance_runner --config configs/acceptance.yaml

replay: ## Replay and verify
	python -m sim.cli.replay --from out/smoke.jsonl --verify-hash

bench: ## Performance benchmark
	python -m sim.cli.bench --agents 300 --ticks 6000 --seed 42

client: ## Build client
	cd client && npm run build

e2e: ## Run E2E tests
	cd client && npx playwright test --reporter=list

clean: ## Clean build artifacts
	rm -rf build dist *.egg-info .pytest_cache .coverage htmlcov .mypy_cache
	rm -rf client/node_modules client/dist
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete