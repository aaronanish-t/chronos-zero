"""Copy-on-write shadow branches using SQLite savepoints.

fork_and_simulate applies a mutation inside SAVEPOINT cow_branch_{id} and keeps it
open so the Z3 verdict can decide: resolve_branch(commit=True) releases it,
commit=False rolls it back. Nothing is committed to production before the verdict.
"""

import sqlite3
import time
import uuid


class CowEngine:
    def __init__(self, db_path: str):
        # isolation_level=None gives us manual transaction control for SAVEPOINT.
        self.conn = sqlite3.connect(db_path, isolation_level=None, check_same_thread=False)
        self.conn.execute("PRAGMA journal_mode=WAL")
        self.conn.execute("PRAGMA synchronous=NORMAL")
        self._open: dict[str, str] = {}

    def fork_and_simulate(self, state_query: str, mutation_sql: str, mutation_params=(), post_query: str = None):
        """Apply a mutation inside a savepoint and return (branch_id, state_pre, state_post, latency_ms).

        state_query / post_query must return a single row; the result is returned as a dict.
        The savepoint is left open until resolve_branch is called.
        """
        t0 = time.perf_counter_ns()
        branch_id = f"cow_{uuid.uuid4().hex[:12]}"
        state_pre = self._row_as_dict(state_query)
        self.conn.execute(f"SAVEPOINT cow_branch_{branch_id}")
        try:
            self.conn.execute(mutation_sql, mutation_params)
            state_post = self._row_as_dict(post_query or state_query)
        except Exception:
            self.conn.execute(f"ROLLBACK TO SAVEPOINT cow_branch_{branch_id}")
            self.conn.execute(f"RELEASE SAVEPOINT cow_branch_{branch_id}")
            raise
        self._open[branch_id] = branch_id
        latency_ms = (time.perf_counter_ns() - t0) / 1_000_000.0
        return branch_id, state_pre, state_post, round(latency_ms, 3)

    def resolve_branch(self, branch_id: str, commit: bool) -> None:
        if branch_id not in self._open:
            raise KeyError(f"unknown or already resolved branch: {branch_id}")
        name = f"cow_branch_{branch_id}"
        if commit:
            self.conn.execute(f"RELEASE SAVEPOINT {name}")
        else:
            self.conn.execute(f"ROLLBACK TO SAVEPOINT {name}")
            self.conn.execute(f"RELEASE SAVEPOINT {name}")
        del self._open[branch_id]

    def _row_as_dict(self, query: str) -> dict:
        cur = self.conn.execute(query)
        cols = [c[0] for c in cur.description]
        row = cur.fetchone()
        return dict(zip(cols, row)) if row else {}
