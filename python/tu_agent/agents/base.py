from __future__ import annotations
from abc import ABC, abstractmethod
from typing import Dict, Any

class Agent(ABC):
    @abstractmethod
    def act(self, obs: Dict[str, Any]) -> int:
        raise NotImplementedError

    def observe(self, obs: Dict[str, Any], action: int, reward: float, next_obs: Dict[str, Any], done: bool) -> None:
        pass
