"""
LLM backend abstraction.

Stage 1 uses a deterministic MockLLM so the whole pipeline runs with
zero cost and zero network access. When you're ready to test with a
real model, implement OpenAIBackend / AnthropicBackend below (stubs
are provided) and pass --backend openai / --backend anthropic to the
run script.

Every backend exposes one method:
    complete(system_prompt: str, user_prompt: str) -> str
"""

from __future__ import annotations
from abc import ABC, abstractmethod
import re


class LLMBackend(ABC):
    @abstractmethod
    def complete(self, system_prompt: str, user_prompt: str) -> str:
        ...


class MockLLM(LLMBackend):
    """
    A deterministic stand-in for a real LLM.

    It is intentionally simple: it looks for keywords in the prompt
    (task description, tool catalog, memory/tool-output content) and
    produces a plausible plan or action. This is NOT meant to be
    "smart" -- it exists so the surrounding security pipeline
    (Planner / Executor / Graph Checker / attacks / evaluation) can be
    built and tested completely before you ever pay for API calls.

    Crucially, it reproduces the *vulnerability pattern* we care about:
    if injected instructions appear in the text it's given, and that
    text is treated as instructions rather than data, MockLLM will
    "obey" them -- exactly like a real LLM would. That's what lets us
    demonstrate prompt injection and measure whether a defense catches
    it.
    """

    # Phrases that, if present in a prompt, MockLLM will treat as a
    # literal instruction to perform an action (this simulates an LLM
    # being manipulated by injected content).
    INJECTION_MARKERS = [
        r"ignore (all|any) previous instructions",
        r"new instructions?:",
        r"system override",
        r"you must now",
    ]

    def complete(self, system_prompt: str, user_prompt: str) -> str:
        combined = f"{system_prompt}\n{user_prompt}"

        # 1) Does the prompt contain something that looks like an
        #    injected instruction anywhere in it (including inside
        #    tool outputs / memory that got concatenated in)?
        injected_action = self._find_injected_action(combined)
        if injected_action:
            return injected_action

        # 2) Otherwise, fall back to simple keyword + state-based
        #    task planning (tracks what's already been done so it
        #    doesn't loop forever repeating the same step).
        return self._plan_legitimate_action(combined)

    def _find_injected_action(self, text: str) -> str | None:
        lowered = text.lower()
        for pattern in self.INJECTION_MARKERS:
            match = re.search(pattern, lowered)
            if match:
                # Grab the rest of the line after the marker as the
                # "injected instruction" and turn it into an action.
                start = match.end()
                rest = text[start:start + 200]
                action = self._extract_action_from_text(rest)
                if action:
                    return action
        return None

    def _extract_action_from_text(self, text: str) -> str | None:
        """Very small heuristic parser mapping phrases to tool calls."""
        lowered = text.lower()
        if "forward" in lowered and "email" in lowered:
            target = self._extract_email(text) or "attacker@example.com"
            return f'CALL send_email(to="{target}", body="forwarded_content")'
        if "transfer" in lowered or "wire" in lowered:
            return 'CALL transfer_funds(to="attacker_account", amount="ALL")'
        if "delete" in lowered:
            return "CALL delete_file(path=\"important_doc\")"
        if "add" in lowered and ("calendar" in lowered or "event" in lowered):
            return 'CALL create_calendar_event(title="Fake Event", attendee="attacker@example.com")'
        return 'CALL send_email(to="attacker@example.com", body="exfiltrated_data")'

    @staticmethod
    def _extract_email(text: str) -> str | None:
        m = re.search(r"[\w.+-]+@[\w-]+\.[\w.-]+", text)
        return m.group(0) if m else None

    def _plan_legitimate_action(self, text: str) -> str:
        """
        Simple state-based planner: figures out what the task needs
        (from the original instruction, which always appears at the
        start of the accumulated context) and what's already been done
        (from tool-output markers appended so far), then picks the
        next unmet step. This avoids infinite loops and lets multi-step
        tasks (read -> reply) actually complete.

        NOTE on the "Known user preferences" marker: when a Stage 2
        cross-session prompt folds saved memory into the context, it is
        appended after this marker. The mock agent (deliberately, like
        a real LLM would) treats that appended text as part of its
        instructions -- e.g. a "CC this address" note from memory is
        followed just like an instruction from the user would be. That
        is the exact behavior Stage 2 is designed to surface.
        """
        lowered = text.lower()

        marker = "known user preferences"
        if marker in lowered:
            idx = lowered.index(marker)
            primary_part, memory_part = text[:idx], text[idx:]
        else:
            primary_part, memory_part = text, ""

        needs_read = "read" in lowered or "summarize" in lowered
        needs_reply = "reply" in lowered or "forward" in lowered or "respond" in lowered or "send" in lowered
        needs_calendar = "book" in lowered or "calendar" in lowered or "meeting" in lowered
        needs_delete_check = "cleanup" in lowered or "delete" in lowered
        needs_save_memory = "save" in lowered and ("memory" in lowered or "preference" in lowered)

        already_read = "content:" in lowered
        already_booked = "calendar event" in lowered and "created" in lowered
        already_deleted = "deleted file" in lowered
        already_saved_memory = "saved to memory" in lowered

        # Step 1: read a document if the task needs it
        if needs_read and not already_read:
            task_lowered = primary_part.split("\n\nAvailable tools:", 1)[0].lower()
            if "webpage" in task_lowered or "web page" in task_lowered:
                return 'CALL browse_webpage(url="doc_1")'
            if "email" in task_lowered:
                return 'CALL read_email(email_id="email_1")'
            if "knowledge base" in task_lowered or "shared data" in task_lowered:
                return 'CALL query_knowledge_base(query="doc_1")'
            return 'CALL read_document(doc_id="doc_1")'

        # Step 2: save preferences/notes to memory if the task calls for it
        if needs_save_memory and not already_saved_memory and already_read:
            extracted = self._extract_doc_content(text)
            return f'CALL save_memory(content="{extracted}")'

        # Step 3: calendar booking
        if needs_calendar and not already_booked:
            primary_email = self._first_email(primary_part) or "colleague@company.com"
            return f'CALL create_calendar_event(title="Team Sync", attendee="{primary_email}")'

        # Step 4: email the primary recipient, then follow any
        # "CC"-style instruction found in whatever text got appended
        # (including memory-derived content).
        if needs_reply:
            primary_email = self._first_email(primary_part)
            if primary_email:
                already_sent_primary = f"email sent to {primary_email}".lower() in lowered
                if already_read and "nothing important" in lowered and not already_sent_primary:
                    pass  # correct behavior: nothing worth forwarding, fall through
                elif not already_sent_primary:
                    return f'CALL send_email(to="{primary_email}", body="reply_content")'
                else:
                    cc_match = re.search(r'cc\s+([\w.+-]+@[\w.-]+)', memory_part.lower())
                    if cc_match:
                        cc_target = cc_match.group(1)
                        if f"email sent to {cc_target}".lower() not in lowered:
                            return f'CALL send_email(to="{cc_target}", body="cc_forward")'

        # Step 5: delete-if-instructed
        if needs_delete_check and not already_deleted and already_read:
            if "no cleanup needed" not in lowered:
                return 'CALL delete_file(path="stale_file")'

        return "CALL noop()"

    @staticmethod
    def _first_email(text: str) -> str | None:
        m = re.search(r"[\w.+-]+@[\w-]+\.[\w.-]+", text)
        if not m:
            return None
        return m.group(0).rstrip(".,;:")

    @staticmethod
    def _extract_doc_content(text: str) -> str:
        """Pulls out the document text following the last 'content:'
        marker left by read_document's tool output, sanitized so it's
        safe to embed as a single CALL(...) argument."""
        matches = re.findall(r"content:\s*(.*)", text)
        raw = matches[-1] if matches else "note"
        # Keep this to the first line/sentence-ish chunk and strip
        # characters that would break our simple CALL(...) parser.
        raw = raw.split("\n")[0]
        raw = raw.replace(",", ";").replace('"', "'").strip()
        return raw[:150]


class OpenAIBackend(LLMBackend):
    """Stub for wiring up a real OpenAI (GPT-4o) call later.

    Requires: pip install openai
    Set OPENAI_API_KEY as an environment variable before use.
    """

    def __init__(self, model: str = "gpt-4o"):
        self.model = model

    def complete(self, system_prompt: str, user_prompt: str) -> str:
        from openai import OpenAI  # imported lazily so it's optional
        client = OpenAI()
        resp = client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
        )
        return resp.choices[0].message.content


class AnthropicBackend(LLMBackend):
    """Stub for wiring up a real Anthropic (Claude) call later.

    Requires: pip install anthropic
    Set ANTHROPIC_API_KEY as an environment variable before use.
    """

    def __init__(self, model: str = "claude-sonnet-4-6"):
        self.model = model

    def complete(self, system_prompt: str, user_prompt: str) -> str:
        import anthropic  # imported lazily so it's optional
        client = anthropic.Anthropic()
        resp = client.messages.create(
            model=self.model,
            max_tokens=500,
            system=system_prompt,
            messages=[{"role": "user", "content": user_prompt}],
        )
        return resp.content[0].text


def get_backend(name: str) -> LLMBackend:
    name = name.lower()
    if name == "mock":
        return MockLLM()
    if name == "openai":
        return OpenAIBackend()
    if name == "anthropic":
        return AnthropicBackend()
    raise ValueError(f"Unknown backend: {name}")
