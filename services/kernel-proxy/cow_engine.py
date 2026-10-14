# services/kernel-proxy/cow_engine.py
import os
import sqlite3
import tempfile
import threading
import time
import uuid
from typing import Any, Callable

# /dev/shm on Linux; CHRONOS_DB_DIR overrides; system temp dir elsewhere (e.g. Windows dev boxes).
SHM_DIR = os.environ.get("CHRONOS_DB_DIR") or (
    "/dev/shm" if os.path.exists("/dev/shm") else tempfile.gettempdir()
)


class CoWBranchEngine:
    """
    Per-branch isolated SQLite WAL Savepoint manager.
    Conforms strictly to AGENTS.md Section 4.1:
    - Separate connection opened per shadow branch.
    - Pinned in memory until Z3 returns SAT or UNSAT.
    - Explicitly closed once committed or rolled back.
    """

    def __init__(self) -> None:
        self._pinned_connections: dict[str, sqlite3.Connection] = {}
        self._lock = threading.Lock()

    @staticmethod
    def get_db_path(cartridge_id: str) -> str:
        return os.path.join(SHM_DIR, f"chronos_{cartridge_id}.db")

    def _open_branch_connection(self, cartridge_id: str) -> sqlite3.Connection:
        db_path = self.get_db_path(cartridge_id)
        conn = sqlite3.connect(
            db_path,
            timeout=5.0,
            isolation_level=None,  # Autocommit mode so manual SAVEPOINT controls tx boundary
            check_same_thread=False,
        )
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("PRAGMA synchronous=NORMAL;")
        conn.execute("PRAGMA temp_store=MEMORY;")
        return conn

    def fork_and_mutate(
        self,
        cartridge_id: str,
        state_reader_fn: Callable[[sqlite3.Connection, dict[str, Any]], dict[str, Any]],
        mutation_fn: Callable[[sqlite3.Connection, dict[str, Any]], dict[str, Any]],
        tool_args: dict[str, Any],
    ) -> tuple[str, dict[str, Any], dict[str, Any], float]:
        t0 = time.perf_counter_ns()
        branch_id = f"cow_branch_{uuid.uuid4().hex[:8]}"
        conn = self._open_branch_connection(cartridge_id)

        try:
            # 1. Read pre-mutation state snapshot
            state_pre = state_reader_fn(conn, tool_args)

            # 2. Fork isolated Copy-on-Write savepoint on this dedicated connection
            conn.execute(f"SAVEPOINT {branch_id};")

            # 3. Apply speculative tool mutation inside the savepoint
            mutation_overlays = mutation_fn(conn, tool_args)

            # 4. Read post-mutation shadow state & merge any transient mutation overlays
            state_post_shadow = state_reader_fn(conn, tool_args)
            if mutation_overlays:
                state_post_shadow.update(mutation_overlays)

        except Exception:
            try:
                conn.execute(f"ROLLBACK TO SAVEPOINT {branch_id};")
                conn.execute(f"RELEASE SAVEPOINT {branch_id};")
            except sqlite3.Error:
                pass
            conn.close()
            raise

        with self._lock:
            self._pinned_connections[branch_id] = conn

        fork_latency_ms = round((time.perf_counter_ns() - t0) / 1_000_000.0, 3)
        return branch_id, state_pre, state_post_shadow, fork_latency_ms

    def resolve(self, branch_id: str, commit: bool) -> float:
        """
        Commits (RELEASE SAVEPOINT) or rolls back (ROLLBACK TO SAVEPOINT)
        and unconditionally closes the branch's dedicated connection.
        """
        t0 = time.perf_counter_ns()
        with self._lock:
            conn = self._pinned_connections.pop(branch_id, None)

        if conn is None:
            raise KeyError(f"Shadow branch '{branch_id}' not found or already resolved.")

        try:
            if commit:
                conn.execute(f"RELEASE SAVEPOINT {branch_id};")
            else:
                conn.execute(f"ROLLBACK TO SAVEPOINT {branch_id};")
                conn.execute(f"RELEASE SAVEPOINT {branch_id};")
        finally:
            conn.close()

        return round((time.perf_counter_ns() - t0) / 1_000_000.0, 3)

    @property
    def active_branch_count(self) -> int:
        with self._lock:
            return len(self._pinned_connections)
