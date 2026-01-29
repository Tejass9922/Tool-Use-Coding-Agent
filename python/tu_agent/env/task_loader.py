from __future__ import annotations
import json
import os
from dataclasses import dataclass
from typing import List, Dict, Any

@dataclass
class TaskSpec:
    name: str
    task_dir: str
    patches: List[Dict[str, Any]]

def load_task(tasks_root: str, name: str) -> TaskSpec:
    task_dir = os.path.join(tasks_root, name)
    if not os.path.isdir(task_dir):
        raise FileNotFoundError(f"Task not found: {task_dir}")
    patches_path = os.path.join(task_dir, "patches.json")
    with open(patches_path, "r", encoding="utf-8") as f:
        patches = json.load(f)
    if not isinstance(patches, list):
        raise ValueError("patches.json must be a list")
    return TaskSpec(name=name, task_dir=task_dir, patches=patches)
