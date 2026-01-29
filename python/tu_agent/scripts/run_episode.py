from __future__ import annotations
import argparse
import os
from tu_agent.env.tool_env import ToolUseCodingEnv
from tu_agent.runner.auto_runner import AutoRunner
from tu_agent.agents.random_agent import RandomAgent
from tu_agent.agents.q_learning import QLearningAgent, QLearnConfig

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--task', default='bugfix_1')
    ap.add_argument('--agent', choices=['random','qlearn'], default='random')
    ap.add_argument('--max-steps', type=int, default=10)
    ap.add_argument('--runner', default=None, help='Path to sandbox_runner binary')
    args = ap.parse_args()

    repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..'))
    tasks_root = os.path.join(repo_root, 'tasks')

    runner_path = args.runner or os.path.join(repo_root, 'rust', 'sandbox_runner', 'target', 'release', 'sandbox_runner')
    runner = AutoRunner(runner_path)

    env = ToolUseCodingEnv(tasks_root=tasks_root, runner=runner, task_name=args.task, max_steps=args.max_steps)

    obs = env.reset()
    if args.agent == 'random':
        agent = RandomAgent(seed=0)
    else:
        agent = QLearningAgent(action_size=obs['action_size'], cfg=QLearnConfig(eps=0.05))

    total = 0.0
    done = False
    while not done:
        a = agent.act(obs)
        next_obs, r, done, info = env.step(a)
        agent.observe(obs, a, r, next_obs, done)
        total += r
        obs = next_obs
        print(f"step={obs['step']:2d} action={a:2d} tool={info.tool:10s} pass={info.pass_rate:.2f} r={r:+.3f} msg={info.message[:120]!r}")
    print(f"TOTAL REWARD: {total:.3f}")
    env.close()

if __name__ == '__main__':
    main()
