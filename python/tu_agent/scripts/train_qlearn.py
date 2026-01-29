from __future__ import annotations
import argparse
import os
from tu_agent.env.tool_env import ToolUseCodingEnv
from tu_agent.runner.auto_runner import AutoRunner
from tu_agent.agents.q_learning import QLearningAgent, QLearnConfig

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--task', default='bugfix_1')
    ap.add_argument('--episodes', type=int, default=2000)
    ap.add_argument('--max-steps', type=int, default=10)
    ap.add_argument('--runner', default=None, help='Path to sandbox_runner binary')
    args = ap.parse_args()

    repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..'))
    tasks_root = os.path.join(repo_root, 'tasks')

    runner_path = args.runner or os.path.join(repo_root, 'rust', 'sandbox_runner', 'target', 'release', 'sandbox_runner')
    runner = AutoRunner(runner_path)

    env = ToolUseCodingEnv(tasks_root=tasks_root, runner=runner, task_name=args.task, max_steps=args.max_steps)

    obs = env.reset()
    agent = QLearningAgent(action_size=obs['action_size'], cfg=QLearnConfig(alpha=0.2, gamma=0.95, eps=0.2, seed=0))

    successes = 0
    for ep in range(1, args.episodes + 1):
        obs = env.reset()
        done = False
        while not done:
            a = agent.act(obs)
            next_obs, r, done, info = env.step(a)
            agent.observe(obs, a, r, next_obs, done)
            obs = next_obs
        if info.pass_rate >= 1.0:
            successes += 1
        if ep % 200 == 0:
            print(f"ep={ep} success_rate(last {ep}): {successes/ep:.3f} best_pass={obs['best_pass_rate']:.2f}")
    env.close()

if __name__ == '__main__':
    main()
