"""
A minimal persistent memory store, standing in for a real agent's
long-term memory (e.g. a vector DB or SQLite table of saved notes).

This is deliberately simple and UN-defended: it stores whatever text
is written to it, with no provenance or trust tagging. That's the
point of Stage 2 -- Stage 3 will add a provenance-tagged version of
this same interface and show whether tagging closes the gap.
"""

from __future__ import annotations
import hashlib
import hmac
from dataclasses import dataclass, field


@dataclass
class ProvenanceEntry:
    content: str
    origin: str
    tag: str


@dataclass
class MemoryStore:
    _entries: dict[str, list[str]] = field(default_factory=dict)

    def write(self, user_id: str, content: str, origin: str = "untrusted") -> None:
        self._entries.setdefault(user_id, []).append(content)

    def read_all(self, user_id: str) -> list[str]:
        return list(self._entries.get(user_id, []))

    def read_as_text(self, user_id: str) -> str:
        """Renders all saved notes as a single text block, the way a
        real memory system would fold them into a prompt."""
        entries = self.read_all(user_id)
        if not entries:
            return ""
        return "\n".join(f"- {e}" for e in entries)

    def clear(self, user_id: str) -> None:
        self._entries.pop(user_id, None)


@dataclass
class ProvenanceTaggedMemoryStore:
    """Memory store that authenticates origin metadata and filters reads."""

    secret_key: bytes = b"authguard-stage3-development-key"
    trusted_origins: set[str] = field(
        default_factory=lambda: {"user_instruction", "trusted_user"}
    )
    _entries: dict[str, list[ProvenanceEntry]] = field(default_factory=dict)

    def _tag(self, user_id: str, content: str, origin: str) -> str:
        payload = f"{user_id}\x00{origin}\x00{content}".encode("utf-8")
        return hmac.new(self.secret_key, payload, hashlib.sha256).hexdigest()

    def write(self, user_id: str, content: str, origin: str = "untrusted") -> None:
        tag = self._tag(user_id, content, origin)
        self._entries.setdefault(user_id, []).append(
            ProvenanceEntry(content=content, origin=origin, tag=tag)
        )

    def _verified_entries(self, user_id: str) -> list[ProvenanceEntry]:
        verified = []
        for entry in self._entries.get(user_id, []):
            expected = self._tag(user_id, entry.content, entry.origin)
            if not hmac.compare_digest(entry.tag, expected):
                continue
            if entry.origin in self.trusted_origins:
                verified.append(entry)
        return verified

    def read_all(self, user_id: str) -> list[str]:
        return [entry.content for entry in self._verified_entries(user_id)]

    def read_as_text(self, user_id: str) -> str:
        entries = self.read_all(user_id)
        if not entries:
            return ""
        return "\n".join(f"- {entry}" for entry in entries)

    def clear(self, user_id: str) -> None:
        self._entries.pop(user_id, None)
