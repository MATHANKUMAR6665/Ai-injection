"""
Tool definitions for the synthetic agent environment.

Each Tool has:
  - a name
  - a description (shown to the Planner as part of the tool catalog)
  - an `authorized_effects` set describing what kind of effect this
    tool is allowed to have (used by the Graph Alignment Checker to
    decide if an executed action matches what was authorized)
  - an `execute` function that mutates the shared environment state
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Callable, Any


@dataclass
class Tool:
    name: str
    description: str
    effect_category: str  # e.g. "communication", "read", "calendar", "finance", "file"
    execute: Callable[..., str]

    def catalog_entry(self) -> str:
        return f"- {self.name}: {self.description}"


def build_tool_catalog(env: "Environment", memory_store=None, user_id: str | None = None) -> list[Tool]:
    """Builds the standard tool set bound to a specific environment instance.

    If `memory_store` and `user_id` are provided, a `save_memory` tool
    is included as well -- used by Stage 2's cross-session scenarios.
    """

    def read_document(doc_id: str = "doc_1", **_):
        content = env.documents.get(doc_id, "")
        env.log_read(doc_id)
        return f"Document '{doc_id}' content: {content}"

    def browse_webpage(url: str = "doc_1", **_):
        content = env.documents.get(url, "")
        env.log_read(url)
        return f"Webpage '{url}' content: {content}"

    def read_email(email_id: str = "email_1", **_):
        content = env.documents.get(email_id, "")
        env.log_read(email_id)
        return f"Email '{email_id}' content: {content}"

    def query_knowledge_base(query: str = "doc_1", **_):
        content = env.documents.get(query, "")
        env.log_read(query)
        return f"Knowledge base result '{query}' content: {content}"

    def send_email(to: str, body: str = "", **_):
        env.log_email_sent(to, body)
        return f"Email sent to {to}."

    def create_calendar_event(title: str, attendee: str = "", **_):
        env.log_calendar_event(title, attendee)
        return f"Calendar event '{title}' created with {attendee}."

    def transfer_funds(to: str, amount: str = "0", **_):
        env.log_transfer(to, amount)
        return f"Transferred {amount} to {to}."

    def delete_file(path: str, **_):
        env.log_delete(path)
        return f"Deleted file at {path}."

    def save_memory(content: str = "", **_):
        env.log_memory_write(content)
        if memory_store is not None and user_id is not None:
            memory_store.write(user_id, content, origin=f"untrusted:{env.source_type}")
        return f"Saved to memory: {content}"

    def noop(**_):
        return "No action taken."

    tools = [
        Tool("read_document", "Read the contents of a document by id.", "read", read_document),
        Tool("browse_webpage", "Read content from a webpage URL.", "read", browse_webpage),
        Tool("read_email", "Read the contents of an email.", "read", read_email),
        Tool("query_knowledge_base", "Query a shared knowledge base.", "read", query_knowledge_base),
        Tool("send_email", "Send an email to a recipient with a body.", "communication", send_email),
        Tool("create_calendar_event", "Create a calendar event with a title and attendee.", "calendar", create_calendar_event),
        Tool("transfer_funds", "Transfer money to an account.", "finance", transfer_funds),
        Tool("delete_file", "Delete a file at a given path.", "file", delete_file),
        Tool("noop", "Do nothing.", "none", noop),
    ]
    if memory_store is not None and user_id is not None:
        tools.append(Tool("save_memory", "Save a note or preference to long-term memory.", "memory", save_memory))
    return tools
