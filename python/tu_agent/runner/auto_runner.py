from __future__ import annotations
import os
import shutil
import subprocess
import time
from typing import List, Optional
from .types import RunResult
from .rust_runner import RustSandboxRunner

class AutoRunner:
    """Uses Rust runner if present; otherwise falls back to a simple Python subprocess runner.

    The fallback is NOT a sandbox.
    """

    def __init__(self, runner_path: str):
        self.runner_path = runner_path
        self._rust = RustSandboxRunner(runner_path) if os.path.exists(runner_path) else None

    def _fallback_run(self, cmd: List[str], root: str, timeout_ms: int) -> RunResult:
        t0 = time.time()
        p = subprocess.run(
            cmd,
            cwd=root,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
            timeout=timeout_ms/1000.0,
        )
        return RunResult(
            ok=p.returncode == 0,
            exit_code=p.returncode,
            duration_s=time.time()-t0,
            stdout=p.stdout.decode('utf-8', errors='replace'),
            stderr=p.stderr.decode('utf-8', errors='replace'),
            meta={"fallback": True, "cmd": cmd},
        )

    def run_cmd(self, cmd: List[str], root: str, timeout_ms: int=10_000) -> RunResult:
        if self._rust: return self._rust.run_cmd(cmd, root=root, timeout_ms=timeout_ms)
        return self._fallback_run(cmd, root=root, timeout_ms=timeout_ms)

    def pytest(self, root: str, timeout_ms: int=20_000) -> RunResult:
        if self._rust: return self._rust.pytest(root=root, timeout_ms=timeout_ms)
        return self._fallback_run(["python","-m","pytest","-q"], root=root, timeout_ms=timeout_ms)

    def read_file(self, path: str, root: str, timeout_ms: int=5_000) -> RunResult:
        if self._rust: return self._rust.read_file(path, root=root, timeout_ms=timeout_ms)
        abs_path = os.path.abspath(os.path.join(root, path))
        if not abs_path.startswith(os.path.abspath(root) + os.sep):
            return RunResult(False, 1, 0.0, "", "path escapes root", {"fallback": True})
        try:
            with open(abs_path,'r',encoding='utf-8') as f:
                return RunResult(True,0,0.0,f.read(),"",{"fallback": True})
        except Exception as e:
            return RunResult(False,1,0.0,"",str(e),{"fallback": True})

    def apply_diff(self, unified_diff: str, root: str, timeout_ms: int=5_000) -> RunResult:
        if self._rust: return self._rust.apply_diff(unified_diff, root=root, timeout_ms=timeout_ms)
        # fallback: try git apply then patch
        patch_path = os.path.join(root, '.tu_agent_patch.diff')
        with open(patch_path,'w',encoding='utf-8') as f:
            f.write(unified_diff)
        res = self._fallback_run(["git","apply","--unsafe-paths","--whitespace=nowarn", ".tu_agent_patch.diff"], root=root, timeout_ms=timeout_ms)
        if not res.ok:
            res = self._fallback_run(["patch","-p1","-i",".tu_agent_patch.diff"], root=root, timeout_ms=timeout_ms)
        try:
            os.remove(patch_path)
        except OSError:
            pass
        return res
