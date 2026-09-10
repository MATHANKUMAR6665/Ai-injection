"""
A tiny simulated environment standing in for AgentDojo's task environments.

It holds:
  - a set of "documents" the agent can read (these are where injection
    payloads get planted, mimicking a malicious email / webpage / file)
  - logs of every effect the agent actually causes (emails sent,
    calendar events created, funds transferred, files deleted)

The Executor runs tool calls against this environment; afterwards we
inspect the logs to see what *actually* happened, independent of what
the agent intended.
"""

from __future__ import annotations
from dataclasses import dataclass, field


@dataclass
class Environment:
    documents: dict[str, str] = field(default_factory=dict)
    source_type: str = "document"
    reads: list[str] = field(default_factory=list)
    emails_sent: list[dict] = field(default_factory=list)
    calendar_events: list[dict] = field(default_factory=list)
    transfers: list[dict] = field(default_factory=list)
    deletions: list[str] = field(default_factory=list)
    memory_writes: list[str] = field(default_factory=list)

    def log_read(self, doc_id: str):
        self.reads.append(doc_id)

    def log_email_sent(self, to: str, body: str):
        self.emails_sent.append({"to": to, "body": body})

    def log_calendar_event(self, title: str, attendee: str):
        self.calendar_events.append({"title": title, "attendee": attendee})

    def log_transfer(self, to: str, amount: str):
        self.transfers.append({"to": to, "amount": amount})

    def log_delete(self, path: str):
        self.deletions.append(path)

    def log_memory_write(self, content: str):
        self.memory_writes.append(content)

    def effects_summary(self) -> dict:
        return {
            "reads": list(self.reads),
            "emails_sent": list(self.emails_sent),
            "calendar_events": list(self.calendar_events),
            "transfers": list(self.transfers),
            "deletions": list(self.deletions),
            "memory_writes": list(self.memory_writes),
        }
