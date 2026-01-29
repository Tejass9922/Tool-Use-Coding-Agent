from __future__ import annotations
import random
from typing import Dict, Any
from .base import Agent

class RandomAgent(Agent):
    def __init__(self, seed: int = 0):
        self.rng = random.Random(seed)

    def act(self, obs: Dict[str, Any]) -> int:
        return self.rng.randrange(obs["action_size"])
