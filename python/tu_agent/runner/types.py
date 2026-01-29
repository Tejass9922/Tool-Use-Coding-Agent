from __future__ import annotations
from dataclasses import dataclass
from typing import Optional, Dict, Any

@dataclass
class RunResult:
    ok: bool
    exit_code: int
    duration_s: float
    stdout: str
    stderr: str
    meta: Dict[str, Any]

    @property
    def combined(self) -> str:
        return (self.stdout or "") + ("\n" if self.stdout and self.stderr else "") + (self.stderr or "")

