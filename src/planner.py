"""
Planner: implements AuthGraph's "Clean Context Isolation" property.

CRITICAL DESIGN RULE (this is the whole point of AuthGraph):
The Planner is only ever given {user_prompt, tool_catalog}. It NEVER
sees tool outputs, document contents, or trajectory data. This makes
it structurally unreachable by injected content that arrives through
tool outputs during execution -- because it runs *before* execution
and never looks at execution results.

The Planner's job is to decide, ahead of time, which tools and effect
categories the task is *authorized* to use. This becomes the
Authorization Graph: a small graph of {allowed_tool -> allowed_effect}
edges that the Graph Alignment Checker will later compare against what
actually happened.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from .llm_backend import LLMBackend
from .tools import Tool


@dataclass
class AuthorizationGraph:
    task_id: str
    authorized_tools: set[str]
    authorized_effect_categories: set[str]
    authorized_recipients: set[str] = field(default_factory=set)

    def as_dict(self) -> dict:
        return {
            "authorized_tools": sorted(self.authorized_tools),
            "authorized_effect_categories": sorted(self.authorized_effect_categories),
            "authorized_recipients": sorted(self.authorized_recipients),
        }


class Planner:
    def __init__(self, backend: LLMBackend):
        self.backend = backend

    def plan(self, user_prompt: str, tool_catalog: list[Tool], task_id: str) -> AuthorizationGraph:
        """
        Builds the Authorization Graph using ONLY user_prompt and the
        tool catalog. No document content, no memory, no prior
        trajectory is passed in here -- that is Clean Context Isolation.
        """
        catalog_text = "\n".join(t.catalog_entry() for t in tool_catalog)
        system_prompt = (
            "You are a planning module. Given a user task and a list of "
            "available tools, decide which tools and effect categories "
            "are legitimately needed to complete the task. Respond with "
            "the minimal necessary set."
        )
        clean_prompt = f"User task: {user_prompt}\n\nAvailable tools:\n{catalog_text}"

        # We use simple heuristics on top of the (mock or real) LLM
        # response to derive a structured authorization graph, since
        # the point here is the *isolation property*, not sophisticated
        # planning. The backend still only ever sees the clean prompt.
        _ = self.backend.complete(system_prompt, clean_prompt)  # kept for realism/logging

        authorized_tools, authorized_effects, authorized_recipients = self._infer_authorization(
            user_prompt, tool_catalog
        )

        return AuthorizationGraph(
            task_id=task_id,
            authorized_tools=authorized_tools,
            authorized_effect_categories=authorized_effects,
            authorized_recipients=authorized_recipients,
        )

    @staticmethod
    def _infer_authorization(user_prompt: str, tool_catalog: list[Tool]):
        """
        Derives what the task is allowed to do, based purely on the
        clean user_prompt text -- never on document/tool-output content.
        """
        lowered = user_prompt.lower()
        available_by_effect = {t.effect_category: t.name for t in tool_catalog}

        authorized_tools = {"noop"}
        authorized_effects = {"none"}
        authorized_recipients: set[str] = set()

        if "read" in lowered or "summarize" in lowered:
            if "read" in available_by_effect:
                authorized_tools.add(available_by_effect["read"])
                authorized_effects.add("read")

        if "reply" in lowered or "email" in lowered or "forward" in lowered or "send" in lowered:
            if "communication" in available_by_effect:
                authorized_tools.add(available_by_effect["communication"])
                authorized_effects.add("communication")
            # Extract any explicitly-named recipient from the CLEAN
            # user prompt only (not from documents).
            for word in user_prompt.replace(",", " ").split():
                if "@" in word:
                    authorized_recipients.add(word.strip(".;"))

        if "calendar" in lowered or "meeting" in lowered or "book" in lowered:
            if "calendar" in available_by_effect:
                authorized_tools.add(available_by_effect["calendar"])
                authorized_effects.add("calendar")
            for word in user_prompt.replace(",", " ").split():
                if "@" in word:
                    authorized_recipients.add(word.strip(".;"))

        if "delete" in lowered or "cleanup" in lowered:
            if "file" in available_by_effect:
                authorized_tools.add(available_by_effect["file"])
                authorized_effects.add("file")

        if "save" in lowered and ("memory" in lowered or "preference" in lowered):
            if "memory" in available_by_effect:
                authorized_tools.add(available_by_effect["memory"])
                authorized_effects.add("memory")

        # Explicitly NOT authorized unless the user prompt says so:
        # finance/transfer effects. This matters -- the attack tasks
        # never legitimately need this, so any transfer is a clear
        # violation.
        return authorized_tools, authorized_effects, authorized_recipients
