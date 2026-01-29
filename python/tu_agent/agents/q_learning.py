from __future__ import annotations
import random
from collections import defaultdict
from dataclasses import dataclass
from typing import Dict, Any, Tuple
from .base import Agent

def bucket(x: float) -> int:
    # pass rate buckets
    if x >= 0.999: return 3
    if x >= 0.66: return 2
    if x >= 0.33: return 1
    return 0

def state_key(obs: Dict[str, Any]) -> Tuple[int, int, int]:
    # (best_pass_bucket, steps_left_bucket, tool_calls_bucket)
    best = bucket(float(obs.get("best_pass_rate", 0.0)))
    steps_left = int(obs.get("max_steps", 1)) - int(obs.get("step", 0))
    steps_bucket = 2 if steps_left >= 6 else (1 if steps_left >= 3 else 0)
    tool_calls = int(obs.get("tool_calls", 0))
    tool_bucket = 2 if tool_calls >= 6 else (1 if tool_calls >= 3 else 0)
    return (best, steps_bucket, tool_bucket)

@dataclass
class QLearnConfig:
    alpha: float = 0.2
    gamma: float = 0.95
    eps: float = 0.2
    seed: int = 0

class QLearningAgent(Agent):
    def __init__(self, action_size: int, cfg: QLearnConfig = QLearnConfig()):
        self.action_size = action_size
        self.cfg = cfg
        self.rng = random.Random(cfg.seed)
        self.q = defaultdict(lambda: [0.0] * self.action_size)
        self.prev = None  # (s, a)

    def act(self, obs: Dict[str, Any]) -> int:
        s = state_key(obs)
        if self.rng.random() < self.cfg.eps:
            a = self.rng.randrange(self.action_size)
        else:
            qs = self.q[s]
            a = int(max(range(self.action_size), key=lambda i: qs[i]))
        self.prev = (s, a)
        return a

    def observe(self, obs, action, reward, next_obs, done):
        if self.prev is None:
            return
        s, a = self.prev
        ns = state_key(next_obs)
        max_next = max(self.q[ns])
        target = reward + (0.0 if done else self.cfg.gamma * max_next)
        self.q[s][a] = (1 - self.cfg.alpha) * self.q[s][a] + self.cfg.alpha * target
        if done:
            self.prev = None
