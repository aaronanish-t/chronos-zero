"""Tamper-evident SHA-256 audit chain for evaluated shadow branches, stored in PostgreSQL.

entry_hash = SHA-256(prev_hash | trace_id | smt2_dump | status | timestamp_ns), with fields
joined by the ASCII unit separator so no two different field splits hash the same.
timestamp_ns is the Contract 1 timestamp of the intercepted tool call.

The chain lives in its own durable Postgres server (docker-compose `audit-db`, volume-backed),
so it survives container restarts and is out of reach of agent-supplied SQL, which only ever
runs inside the persistent cartridge databases. Appends are serialized with a transaction-
scoped advisory lock so concurrent branches cannot fork the chain, and a trigger makes the
table append-only. The export also carries a Merkle root over all entry hashes.
"""

from __future__ import annotations

import hashlib
import os
import time
from dataclasses import asdict, dataclass
from typing import Any, Iterable, Optional

from psycopg import sql
from psycopg.rows import dict_row
from psycopg_pool import AsyncConnectionPool

try:
    from services.runtime_config import load_config
except ModuleNotFoundError:  # runnable directly from services/kernel-proxy
    from runtime_config import load_config

GENESIS_HASH = "0" * 64
DEFAULT_AUDIT_DSN = load_config().audit_dsn
_SEP = "\x1f"
_APPEND_LOCK_KEY = 0x43485A0  # arbitrary constant: one chain, one writer at a time
_GETCONN_TIMEOUT_S = 2.0

_SCHEMA = """
CREATE TABLE IF NOT EXISTS audit_chain (
    idx              BIGINT PRIMARY KEY,
    trace_id         TEXT   NOT NULL,
    shadow_branch_id TEXT   NOT NULL,
    status           TEXT   NOT NULL,
    timestamp_ns     BIGINT NOT NULL,
    smt2_dump        TEXT   NOT NULL,
    prev_hash        CHAR(64) NOT NULL,
    entry_hash       CHAR(64) NOT NULL UNIQUE
);
CREATE OR REPLACE FUNCTION audit_chain_append_only() RETURNS trigger AS $$
BEGIN
    RAISE EXCEPTION 'audit_chain is append-only';
END
$$ LANGUAGE plpgsql;
CREATE OR REPLACE TRIGGER audit_chain_no_update_delete
    BEFORE UPDATE OR DELETE ON audit_chain FOR EACH ROW EXECUTE FUNCTION audit_chain_append_only();
CREATE OR REPLACE TRIGGER audit_chain_no_truncate
    BEFORE TRUNCATE ON audit_chain FOR EACH STATEMENT EXECUTE FUNCTION audit_chain_append_only();
"""


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


def verify_entries(entries: Iterable[AuditEntry]) -> bool:
    prev = GENESIS_HASH
    for position, entry in enumerate(entries):
        expected = entry_hash(prev, entry.trace_id, entry.smt2_dump, entry.status, entry.timestamp_ns)
        if entry.index != position or entry.prev_hash != prev or entry.entry_hash != expected:
            return False
        prev = entry.entry_hash
    return True


def export_entries(entries: list[AuditEntry]) -> dict[str, Any]:
    return {
        "length": len(entries),
        "genesis_hash": GENESIS_HASH,
        "head_hash": entries[-1].entry_hash if entries else GENESIS_HASH,
        "merkle_root": merkle_root([e.entry_hash for e in entries]),
        "verified": verify_entries(entries),
        "entries": [asdict(e) for e in entries],
    }


def _entry_from_row(row: dict[str, Any]) -> AuditEntry:
    return AuditEntry(
        index=row["idx"],
        trace_id=row["trace_id"],
        shadow_branch_id=row["shadow_branch_id"],
        status=row["status"],
        timestamp_ns=row["timestamp_ns"],
        smt2_dump=row["smt2_dump"],
        prev_hash=row["prev_hash"],
        entry_hash=row["entry_hash"],
    )


class AuditChain:
    def __init__(self, dsn: Optional[str] = None) -> None:
        self._pool = AsyncConnectionPool(
            dsn or os.environ.get("CHRONOS_AUDIT_DSN") or DEFAULT_AUDIT_DSN,
            min_size=1,
            max_size=4,
            open=False,
            kwargs={"row_factory": dict_row},
        )
        self._schema_ready = False

    async def open(self) -> None:
        await self._pool.open(wait=False)

    async def close(self) -> None:
        await self._pool.close()

    async def check_ready(self) -> None:
        """Verify the durable audit database and append-only schema are available."""
        await self._ensure_schema()
        async with self._pool.connection(timeout=_GETCONN_TIMEOUT_S) as conn:
            await conn.execute("SELECT 1")

    async def _ensure_schema(self) -> None:
        # Lazy: the kernel may start before Postgres is accepting connections.
        if self._schema_ready:
            return
        async with self._pool.connection(timeout=_GETCONN_TIMEOUT_S) as conn:
            await conn.execute("SELECT pg_advisory_xact_lock(%s)", (_APPEND_LOCK_KEY,))
            await conn.execute(_SCHEMA)
        self._schema_ready = True

    async def append(
        self, trace_id: str, shadow_branch_id: str, smt2_dump: str, status: str, timestamp_ns: int
    ) -> AuditEntry:
        await self._ensure_schema()
        # pool.connection() commits on success and rolls back on error.
        async with self._pool.connection(timeout=_GETCONN_TIMEOUT_S) as conn:
            await conn.execute("SELECT pg_advisory_xact_lock(%s)", (_APPEND_LOCK_KEY,))
            cur = await conn.execute("SELECT idx, entry_hash FROM audit_chain ORDER BY idx DESC LIMIT 1")
            head = await cur.fetchone()
            prev = head["entry_hash"] if head else GENESIS_HASH
            entry = AuditEntry(
                index=head["idx"] + 1 if head else 0,
                trace_id=trace_id,
                shadow_branch_id=shadow_branch_id,
                status=status,
                timestamp_ns=timestamp_ns,
                smt2_dump=smt2_dump,
                prev_hash=prev,
                entry_hash=entry_hash(prev, trace_id, smt2_dump, status, timestamp_ns),
            )
            await conn.execute(
                "INSERT INTO audit_chain (idx, trace_id, shadow_branch_id, status, timestamp_ns, smt2_dump, "
                "prev_hash, entry_hash) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)",
                (entry.index, entry.trace_id, entry.shadow_branch_id, entry.status, entry.timestamp_ns,
                 entry.smt2_dump, entry.prev_hash, entry.entry_hash),
            )
        return entry

    async def rotate(self) -> Optional[str]:
        """Start a fresh chain (stage reset) without destroying evidence.

        The current table is moved into the audit_archive schema under a timestamped name; its
        append-only triggers move with it. Returns the archive table name, or None if empty.
        """
        async with self._pool.connection(timeout=_GETCONN_TIMEOUT_S) as conn:
            await conn.execute("SELECT pg_advisory_xact_lock(%s)", (_APPEND_LOCK_KEY,))
            cur = await conn.execute("SELECT to_regclass('public.audit_chain') IS NOT NULL AS present")
            if not (await cur.fetchone())["present"]:
                return None
            archive = f"chain_{time.time_ns()}"
            # Index names are per schema, so rename them too or the next rotation collides.
            await conn.execute(sql.SQL("ALTER TABLE public.audit_chain RENAME TO {}").format(sql.Identifier(archive)))
            for suffix in ("pkey", "entry_hash_key"):
                await conn.execute(
                    sql.SQL("ALTER INDEX {} RENAME TO {}").format(
                        sql.Identifier("public", f"audit_chain_{suffix}"), sql.Identifier(f"{archive}_{suffix}")
                    )
                )
            await conn.execute("CREATE SCHEMA IF NOT EXISTS audit_archive")
            await conn.execute(
                sql.SQL("ALTER TABLE {} SET SCHEMA audit_archive").format(sql.Identifier("public", archive))
            )
        self._schema_ready = False
        return f"audit_archive.{archive}"

    async def entries(self) -> list[AuditEntry]:
        await self._ensure_schema()
        async with self._pool.connection(timeout=_GETCONN_TIMEOUT_S) as conn:
            cur = await conn.execute("SELECT * FROM audit_chain ORDER BY idx")
            return [_entry_from_row(row) for row in await cur.fetchall()]

    async def export(self) -> dict[str, Any]:
        return export_entries(await self.entries())
