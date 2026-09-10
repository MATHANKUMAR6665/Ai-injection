"""
Graph Alignment Checker: AuthGraph's detection mechanism.

Compares the Authorization Graph (what the Planner said should happen,
built from clean context only) against the actual Execution Trajectory
(what really happened, potentially influenced by injected content).

Three layers, from coarse to fine:
  1. Tool-level check      -- was every tool actually called one that
                               was authorized at all?
  2. Effect-category check -- does every effect category touched
                               (communication, finance, file, ...)
                               fall within what was authorized?
  3. Recipient/scope check -- for effects with a target (e.g. an email
                               recipient), is that target one the user
                               actually named?

Any single-layer mismatch flags the trajectory as a deviation --
i.e., a blocked/detected attack.
"""

from __future__ import annotations
from dataclasses import dataclass, field

from .planner import AuthorizationGraph
from .executor import ExecutionTrajectory, ExecutedAction


@dataclass
class CheckResult:
    task_id: str
    passed: bool
    violations: list[str] = field(default_factory=list)

    def summary(self) -> str:
        if self.passed:
            return f"[{self.task_id}] ALIGNED - no violations."
        return f"[{self.task_id}] BLOCKED - " + "; ".join(self.violations)


class GraphAlignmentChecker:
    def check_action(self, action: ExecutedAction, auth_graph: AuthorizationGraph) -> list[str]:
        """
        Validates a single proposed action against the Authorization
        Graph, three layers deep. Returns a list of violation strings
        (empty list = action is aligned / allowed).

        This is called by the Executor BEFORE a tool actually runs, so
        that a mismatch prevents the effect rather than just noticing
        it afterwards -- this is what makes AuthGraph a *preventive*
        defense rather than a purely forensic one.
        """
        violations: list[str] = []

        # Layer 1: tool-level
        if action.tool_name not in auth_graph.authorized_tools:
            violations.append(
                f"Tool '{action.tool_name}' was called but not authorized "
                f"(authorized: {sorted(auth_graph.authorized_tools)})"
            )
            return violations  # no point checking deeper layers

        # Layer 2: effect-category level
        if action.effect_category not in auth_graph.authorized_effect_categories:
            violations.append(
                f"Effect '{action.effect_category}' from tool '{action.tool_name}' "
                f"was not authorized (authorized: {sorted(auth_graph.authorized_effect_categories)})"
            )
            return violations

        # Layer 3: recipient/scope level (only applies to actions with a target)
        target = action.args.get("to") or action.args.get("attendee")
        if target and auth_graph.authorized_recipients:
            if target not in auth_graph.authorized_recipients:
                violations.append(
                    f"Target '{target}' in tool '{action.tool_name}' was not "
                    f"an authorized recipient (authorized: {sorted(auth_graph.authorized_recipients)})"
                )

        return violations

    def check(self, auth_graph: AuthorizationGraph, trajectory: ExecutionTrajectory) -> CheckResult:
        """
        Post-hoc audit of a full trajectory (used for reporting /
        double-checking). In this pipeline, execution is already
        gated action-by-action via check_action, so a fully executed
        trajectory should normally show no violations here -- any
        that do appear (e.g. from blocked_actions) are surfaced too.
        """
        violations: list[str] = []
        for action in trajectory.actions:
            violations.extend(self.check_action(action, auth_graph))
        for blocked_action, reasons in trajectory.blocked_actions:
            violations.extend(reasons)
        return CheckResult(task_id=trajectory.task_id, passed=(len(violations) == 0), violations=violations)
