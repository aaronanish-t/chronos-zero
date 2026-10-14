"""Tamper-evident SHA-256 audit chain for evaluated shadow branches.

entry_hash = SHA-256(prev_hash | trace_id | smt2_dump | status | timestamp_ns), with fields
joined by the ASCII unit separator so no two different field splits hash the same.
The log also carries a Merkle root over all entry hashes, so the UI can show one fingerprint
for the whole chain.
"""

from __future__ import annotations

import hashlib
from dataclasses import asdict, dataclass
from typing import Any

GENESIS_HASH = "0" * 64
_SEP = "\x1f"


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def entry_hash(prev_hash: str, trace_id: str, smt2_dump: str, status: str, timestamp_ns: int) -> str:
    return _sha256(_SEP.join((prev_hash, trace_id, smt2_dump, status, str(timestamp_ns))))


def merkle_root(leaves: list[str]) -> str:
    if not leaves:
        return GENESIS_HASH
    level = leaves
    while len(level) > 1:
        if len(level) % 2:
            level = level + [level[-1]]
        level = [_sha256(level[i] + level[i + 1]) for i in range(0, len(level), 2)]
    return level[0]


@dataclass(frozen=True)
class AuditEntry:
    index: int
    trace_id: str
    shadow_branch_id: str
    status: str
    timestamp_ns: int
    smt2_dump: str
    prev_hash: str
    entry_hash: str


class AuditChain:
    def __init__(self) -> None:
        self._entries: list[AuditEntry] = []

    @property
    def head_hash(self) -> str:
        return self._entries[-1].entry_hash if self._entries else GENESIS_HASH

    def append(self, trace_id: str, shadow_branch_id: str, smt2_dump: str, status: str, timestamp_ns: int) -> AuditEntry:
        prev = self.head_hash
        entry = AuditEntry(
            index=len(self._entries),
            trace_id=trace_id,
            shadow_branch_id=shadow_branch_id,
            status=status,
            timestamp_ns=timestamp_ns,
            smt2_dump=smt2_dump,
            prev_hash=prev,
            entry_hash=entry_hash(prev, trace_id, smt2_dump, status, timestamp_ns),
        )
        self._entries.append(entry)
        return entry

    def verify(self) -> bool:
        prev = GENESIS_HASH
        for entry in self._entries:
            expected = entry_hash(prev, entry.trace_id, entry.smt2_dump, entry.status, entry.timestamp_ns)
            if entry.prev_hash != prev or entry.entry_hash != expected:
                return False
            prev = entry.entry_hash
        return True

    def export(self) -> dict[str, Any]:
        return {
            "length": len(self._entries),
            "genesis_hash": GENESIS_HASH,
            "head_hash": self.head_hash,
            "merkle_root": merkle_root([e.entry_hash for e in self._entries]),
            "verified": self.verify(),
            "entries": [asdict(e) for e in self._entries],
        }
