from __future__ import annotations
import json
import os
import subprocess
from dataclasses import asdict
from typing import List, Optional, Dict, Any
from .types import RunResult

class RustSandboxRunner:
    """Thin wrapper around the Rust `sandbox_runner` CLI.

    It expects a binary at `runner_path`. By default we look in the repo
    at: rust/sandbox_runner/target/release/sandbox_runner
    """

    def __init__(self, runner_path: str):
        self.runner_path = runner_path

    def _call(self, args: List[str], root: str, timeout_ms: int, stdin: Optional[str]=None) -> RunResult:
        cmd = [self.runner_path] + args + ["--root", root, "--timeout-ms", str(timeout_ms)]
        try:
            p = subprocess.run(
                cmd,
                input=stdin.encode("utf-8") if stdin is not None else None,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=False,
            )
        except FileNotFoundError as e:
            raise RuntimeError(f"Rust runner not found at: {self.runner_path}. Build it with cargo.") from e

        # The runner prints JSON on stdout; if it fails, keep raw.
        stdout = p.stdout.decode("utf-8", errors="replace")
        stderr = p.stderr.decode("utf-8", errors="replace")

        try:
            payload = json.loads(stdout) if stdout.strip().startswith("{") else None
        except json.JSONDecodeError:
            payload = None

        if isinstance(payload, dict) and "ok" in payload:
            return RunResult(
                ok=bool(payload.get("ok")),
                exit_code=int(payload.get("exit_code", p.returncode)),
                duration_s=float(payload.get("duration_s", 0.0)),
                stdout=str(payload.get("stdout", "")),
                stderr=str(payload.get("stderr", "")),
                meta={k:v for k,v in payload.items() if k not in {"ok","exit_code","duration_s","stdout","stderr"}},
            )

        return RunResult(
            ok=(p.returncode == 0),
            exit_code=p.returncode,
            duration_s=0.0,
            stdout=stdout,
            stderr=stderr,
            meta={"raw": True},
        )

    def run_cmd(self, cmd: List[str], root: str, timeout_ms: int=10_000) -> RunResult:
        return self._call(["run", "--"] + cmd, root=root, timeout_ms=timeout_ms)

    def pytest(self, root: str, timeout_ms: int=20_000) -> RunResult:
        return self._call(["pytest"], root=root, timeout_ms=timeout_ms)

    def read_file(self, path: str, root: str, timeout_ms: int=5_000) -> RunResult:
        return self._call(["read-file", "--path", path], root=root, timeout_ms=timeout_ms)

    def apply_diff(self, unified_diff: str, root: str, timeout_ms: int=5_000) -> RunResult:
        # patch is read from stdin
        return self._call(["apply-diff"], root=root, timeout_ms=timeout_ms, stdin=unified_diff)
