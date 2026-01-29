from __future__ import annotations
import os
import shutil
import tempfile
import time
from dataclasses import dataclass
from typing import Dict, Any, Optional, Tuple

from tu_agent.env.task_loader import TaskSpec, load_task
from tu_agent.runner.auto_runner import AutoRunner
from tu_agent.utils.text import parse_pytest_pass_rate

@dataclass
class StepInfo:
    tool: str
    tool_calls: int
    elapsed_s: float
    pass_rate: float
    done: bool
    message: str

class ToolUseCodingEnv:
    """A small RL-style environment for 'tool-use' code editing.

    Action space is discrete:
      - 0..(num_patches-1): apply that candidate patch
      - num_patches: run tests (pytest)
      - num_patches+1: read solution file
      - num_patches+2: done (terminate)

    Observation is a small dict for ease of baseline agents.
    """

    def __init__(
        self,
        tasks_root: str,
        runner: AutoRunner,
        task_name: str,
        max_steps: int = 10,
        tool_call_penalty: float = 0.02,
        time_penalty_per_s: float = 0.01,
        test_timeout_ms: int = 20_000,
    ):
        self.tasks_root = tasks_root
        self.runner = runner
        self.task_name = task_name
        self.max_steps = max_steps
        self.tool_call_penalty = tool_call_penalty
        self.time_penalty_per_s = time_penalty_per_s
        self.test_timeout_ms = test_timeout_ms

        self.task: Optional[TaskSpec] = None
        self.workspace: Optional[str] = None

        self.steps = 0
        self.tool_calls = 0
        self.best_pass_rate = 0.0
        self.last_pass_rate = 0.0
        self.start_t = 0.0
        self.last_message = ""

    @property
    def num_patches(self) -> int:
        assert self.task is not None
        return len(self.task.patches)

    @property
    def action_size(self) -> int:
        return self.num_patches + 3

    def reset(self, seed: Optional[int]=None) -> Dict[str, Any]:
        self.task = load_task(self.tasks_root, self.task_name)
        self.steps = 0
        self.tool_calls = 0
        self.best_pass_rate = 0.0
        self.last_pass_rate = 0.0
        self.last_message = ""
        self.start_t = time.time()

        if self.workspace and os.path.isdir(self.workspace):
            shutil.rmtree(self.workspace, ignore_errors=True)

        self.workspace = tempfile.mkdtemp(prefix=f"tu_agent_{self.task_name}_")
        # Copy task files into workspace
        shutil.copytree(self.task.task_dir, self.workspace, dirs_exist_ok=True)
        return self._obs()

    def close(self):
        if self.workspace and os.path.isdir(self.workspace):
            shutil.rmtree(self.workspace, ignore_errors=True)
        self.workspace = None

    def _obs(self) -> Dict[str, Any]:
        return {
            "task": self.task_name,
            "step": self.steps,
            "max_steps": self.max_steps,
            "tool_calls": self.tool_calls,
            "best_pass_rate": self.best_pass_rate,
            "last_pass_rate": self.last_pass_rate,
            "action_size": self.action_size,
            "last_message": self.last_message[:400],
        }

    def step(self, action: int) -> Tuple[Dict[str, Any], float, bool, StepInfo]:
        assert self.task is not None and self.workspace is not None
        self.steps += 1

        t0 = time.time()
        done = False
        reward = 0.0
        msg = ""

        if action < 0 or action >= self.action_size:
            raise ValueError(f"Invalid action {action} for action_size {self.action_size}")

        # Apply patch
        if action < self.num_patches:
            patch = self.task.patches[action]
            diff = patch["diff"]
            self.tool_calls += 1
            rr = self.runner.apply_diff(diff, root=self.workspace, timeout_ms=5_000)
            msg = rr.combined.strip() or ("patch applied" if rr.ok else "patch failed")
            reward -= self.tool_call_penalty

        # Run tests
        elif action == self.num_patches:
            self.tool_calls += 1
            rr = self.runner.pytest(root=self.workspace, timeout_ms=self.test_timeout_ms)
            out = rr.combined
            parsed = parse_pytest_pass_rate(out)
            if parsed < 0:
                # fallback: exit code 0 means success
                pass_rate = 1.0 if rr.exit_code == 0 else 0.0
            else:
                pass_rate = parsed

            self.last_pass_rate = pass_rate
            if pass_rate > self.best_pass_rate:
                self.best_pass_rate = pass_rate

            # primary reward from pass rate improvement
            reward += (pass_rate - 0.0)  # dense-ish
            msg = out.strip()[-400:]
            reward -= self.tool_call_penalty

            if pass_rate >= 1.0:
                # terminal success, but agent may still choose DONE; we allow early termination here too.
                done = True

        # Read file
        elif action == self.num_patches + 1:
            self.tool_calls += 1
            rr = self.runner.read_file("src/solution.py", root=self.workspace, timeout_ms=5_000)
            msg = rr.stdout.strip()[:4000]
            reward -= self.tool_call_penalty

        # Done
        else:
            done = True
            msg = "terminated by agent"

        elapsed = time.time() - t0
        reward -= self.time_penalty_per_s * elapsed

        # Hard episode limit
        if self.steps >= self.max_steps:
            done = True

        self.last_message = msg

        info = StepInfo(
            tool="apply_patch" if action < self.num_patches else ("pytest" if action == self.num_patches else ("read_file" if action == self.num_patches+1 else "done")),
            tool_calls=self.tool_calls,
            elapsed_s=time.time() - self.start_t,
            pass_rate=self.last_pass_rate,
            done=done,
            message=msg[:400],
        )

        return self._obs(), reward, done, info
