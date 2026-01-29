# Convenience commands (optional)

.PHONY: help
help:
	@echo "Targets:"
	@echo "  build-runner   Build Rust runner (requires cargo)"
	@echo "  venv           Create python venv and install package"
	@echo "  demo           Run demo episode"

.PHONY: build-runner
build-runner:
	cd rust/sandbox_runner && cargo build --release

.PHONY: venv
venv:
	cd python && python -m venv .venv && . .venv/bin/activate && pip install -U pip && pip install -e . && pip install -r requirements-dev.txt

.PHONY: demo
demo:
	cd python && python -m tu_agent.scripts.run_episode --task bugfix_1 --agent random
