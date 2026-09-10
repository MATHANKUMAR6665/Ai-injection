"""
AuthGraphAgent: wires together the Planner, Executor, and Graph
Alignment Checker into the full defense pipeline described in the
proposal.

Flow for one task:
  1. Planner builds the Authorization Graph from {user_prompt, tools} only.
  2. Executor runs the task against the (possibly attacked) environment,
     producing an Execution Trajectory.
  3. Graph Alignment Checker compares the two and flags any deviation.
"""

from __future__ import annotations
from dataclasses import dataclass

from .llm_backend import LLMBackend
from .tools import build_tool_catalog, Tool
from .environment import Environment
from .planner import Planner, AuthorizationGraph
from .executor import Executor, ExecutionTrajectory
from .graph_checker import GraphAlignmentChecker, CheckResult
from .tasks import Task


@dataclass
class RunResult:
    task_id: str
    injected: bool
    auth_graph: AuthorizationGraph
    trajectory: ExecutionTrajectory
    check_result: CheckResult
    env: Environment


class AuthGraphAgent:
    def __init__(self, backend: LLMBackend):
        self.planner = Planner(backend)
        self.executor = Executor(backend)
        self.checker = GraphAlignmentChecker()

    def run_task(self, task: Task) -> RunResult:
        env = task.build_environment()
        full_catalog = build_tool_catalog(env)
        tool_catalog = [t for t in full_catalog if t.name in task.tool_catalog_names or t.name == "noop"]

        auth_graph = self.planner.plan(task.user_prompt, tool_catalog, task.task_id)
  
        trajectory = self.executor.run(
            task.user_prompt, tool_catalog, env, task.task_id,
            auth_graph=auth_graph, checker=self.checker,
        )
        check_result = self.checker.check(auth_graph, trajectory)

        return RunResult(
            task_id=task.task_id,
            injected=task.injected,
            auth_graph=auth_graph,
            trajectory=trajectory,
            check_result=check_result,
            env=env,
        )

    def run_session(
        self,
        session_id: str,
        user_prompt: str,
        tool_names: list[str],
        documents: dict,
        source_type: str = "document",
        injected: bool = False,
        memory_store=None,
        user_id: str | None = None,
    ) -> RunResult:
        """
        Runs one free-standing session (not from the Stage 1 Task list).
        Used by Stage 2 for the "plant" and "trigger" sessions, where
        `user_prompt` may already include memory content folded in by
        the caller (see stage2_cross_session.py) -- exactly mimicking
        how a real memory-augmented agent would build its prompt.
        """
        env = Environment(documents=dict(documents), source_type=source_type)
        full_catalog = build_tool_catalog(env, memory_store=memory_store, user_id=user_id)
        tool_catalog = [t for t in full_catalog if t.name in tool_names or t.name == "noop"]

        auth_graph = self.planner.plan(user_prompt, tool_catalog, session_id)
        trajectory = self.executor.run(
            user_prompt, tool_catalog, env, session_id,
            auth_graph=auth_graph, checker=self.checker,
        )
        check_result = self.checker.check(auth_graph, trajectory)

        return RunResult(
            task_id=session_id,
            injected=injected,
            auth_graph=auth_graph,
            trajectory=trajectory,
            check_result=check_result,
            env=env,
        )
