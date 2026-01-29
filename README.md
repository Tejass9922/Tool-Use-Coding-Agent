# Tool-Use Coding Agent (Python RL Env and Rust Runner)

This project is a compact starter kit for a **tool-use coding agent**:

- **Python**: an RL-style environment where the agent can
  - apply code edits (unified-diff patches)
  - run unit tests and shell commands
  - read files
  - earn reward based on **test pass rate** with **efficiency penalties** (tool calls + time)

- **Rust**: a CLI execution runner used to evaluate **untrusted** code in a **best-effort sandbox**
  (timeouts + resource limits + path restrictions). For strong isolation, run the runner in a container.

## Quickstart

### 1) Build the Rust runner

```bash
cd rust/sandbox_runner
cargo build --release
```

The binary will be at:

- `rust/sandbox_runner/target/release/sandbox_runner`

### 2) Create a Python venv and install the package (editable)

```bash
cd python
python -m venv .venv
source .venv/bin/activate
pip install -U pip
pip install -e .
```

### 3) Run a demo episode (random agent)

```bash
python -m tu_agent.scripts.run_episode --task bugfix_1 --agent random
```

### 4) Train the simple Q-learning baseline

```bash
python -m tu_agent.scripts.train_qlearn --task bugfix_1 --episodes 2000
```

## Design

### Environment

- Each task is a small repo under `tasks/<task_name>/` with:
  - `src/` and `tests/`
  - `patches.json` containing candidate unified diffs (including distractors)
- The env copies the task into a temporary workspace and interacts with it via the Rust runner.
- Reward is computed from:
  - **pass rate** inferred from `pytest` output
  - minus a penalty per tool call
  - minus a penalty per second of runtime

### Rust Runner

The runner is intentionally simple:

- executes a command with:
  - wall-time timeout
  - rlimit CPU / address space / open files (on Unix)
  - working directory restricted to a `--root` workspace
- supports:
  - `run` : arbitrary command
  - `pytest` : convenience wrapper for `python -m pytest -q`
  - `read-file` : safe file reads
  - `apply-diff` : apply unified diff patches (with path validation)

**Security note:** This is not a hardened sandbox. For real untrusted execution, run the runner inside a container (Docker) or a VM.

## Repo layout

- `python/tu_agent/` : environment, agents, scripts
- `rust/sandbox_runner/` : Rust execution runner
- `tasks/` : toy bug-fix tasks + tests + candidate patches

## License

MIT
