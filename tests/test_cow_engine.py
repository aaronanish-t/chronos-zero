import time

import pytest

from cow_engine import CoWBranchEngine, run_migration
from pg_support import pg_query, reset_databases, run

CARTRIDGE = "FINTECH_ESCROW"


@pytest.fixture
def dsn():
    return reset_databases()


async def read_balance(conn, _tool_call):
    cur = await conn.execute("SELECT balance FROM cow_test_accounts WHERE id = 1")
    return {"balance": (await cur.fetchone())["balance"]}


async def debit(conn, tool_call):
    await conn.execute(
        "UPDATE cow_test_accounts SET balance = balance - %s WHERE id = 1", (tool_call["amount"],)
    )
    return {}


def committed_balance():
    return pg_query(CARTRIDGE, "SELECT balance FROM cow_test_accounts WHERE id = 1")[0][0]


def with_engine(dsn, scenario):
    """Run an async scenario against a freshly opened engine."""
    async def main():
        engine = CoWBranchEngine(dsn, [CARTRIDGE])
        await engine.open()
        try:
            return await scenario(engine)
        finally:
            await engine.close()
    return run(main())


def test_shadow_mutation_visible_then_rolled_back(dsn):
    async def scenario(engine):
        bid, pre, post, _ = await engine.fork_and_mutate(CARTRIDGE, read_balance, debit, {"amount": 4000})
        assert (pre["balance"], post["balance"]) == (5000, 1000)
        await engine.resolve(bid, commit=False)
        assert engine.active_branch_count == 0
    with_engine(dsn, scenario)
    assert committed_balance() == 5000


def test_commit_persists_mutation(dsn):
    async def scenario(engine):
        bid, _, _, _ = await engine.fork_and_mutate(CARTRIDGE, read_balance, debit, {"amount": 400})
        await engine.resolve(bid, commit=True)
    with_engine(dsn, scenario)
    assert committed_balance() == 4600


def test_uncommitted_branch_invisible_to_other_connections(dsn):
    async def scenario(engine):
        bid, _, _, _ = await engine.fork_and_mutate(CARTRIDGE, read_balance, debit, {"amount": 4000})
        assert committed_balance() == 5000
        await engine.resolve(bid, commit=False)
    with_engine(dsn, scenario)


def test_mutation_overlay_merged_into_post_state(dsn):
    async def overlay(conn, tool_call):
        await debit(conn, tool_call)
        return {"iban_allowlisted": False}

    async def scenario(engine):
        bid, _, post, _ = await engine.fork_and_mutate(CARTRIDGE, read_balance, overlay, {"amount": 1})
        assert post == {"balance": 4999, "iban_allowlisted": False}
        await engine.resolve(bid, commit=False)
    with_engine(dsn, scenario)


def test_mutation_failure_rolls_back_and_unpins(dsn):
    async def boom(conn, tool_call):
        await debit(conn, tool_call)
        raise RuntimeError("tool failed")

    async def scenario(engine):
        with pytest.raises(RuntimeError):
            await engine.fork_and_mutate(CARTRIDGE, read_balance, boom, {"amount": 4000})
        assert engine.active_branch_count == 0
    with_engine(dsn, scenario)
    assert committed_balance() == 5000


def test_double_resolve_raises(dsn):
    async def scenario(engine):
        bid, _, _, _ = await engine.fork_and_mutate(CARTRIDGE, read_balance, debit, {"amount": 1})
        await engine.resolve(bid, commit=False)
        with pytest.raises(KeyError):
            await engine.resolve(bid, commit=True)
    with_engine(dsn, scenario)


class RecordingConn:
    """Stands in for the pinned connection: records each statement run_migration would send."""

    def __init__(self):
        self.sent = []

    async def execute(self, statement):
        self.sent.append(statement)


def migrate(sql):
    conn = RecordingConn()
    run(run_migration(conn, {"arguments": {"sql": sql}}))
    return conn.sent


@pytest.mark.parametrize("sql", [
    "/**/COMMIT",
    "-- x\nCOMMIT",
    "-- x\rROLLBACK",
    "/* outer /* nested */ still a comment */ COMMIT",
    "  /**/ SET statement_timeout = 0",
    "DELETE FROM users; /**/COMMIT",
    "SELECT set_config('statement_timeout', '0', false)",
    'SELECT "pg_terminate_backend"(42)',
    "SELECT pg_advisory_lock(1)",
    r"""SELECT U&"\0073et_config"('lock_timeout', '0', false)""",
    "SELECT set_config/**/('statement_timeout','0',false)",
    "SELECT pg_catalog.set_config /* x */ ('lock_timeout','0',false)",
    "SELECT pg_terminate_backend--x\n(42)",
    "ALTER ROLE chronos_kernel SET statement_timeout = 0",
])
def test_run_migration_rejects_sql_that_escapes_the_shadow_branch(sql):
    with pytest.raises(PermissionError):
        migrate(sql)


def test_run_migration_guard_is_linear_in_comment_count():
    # Quadratic scanning took about 1 s per 0.6 MB, blocking the kernel's event loop meanwhile.
    started = time.perf_counter()
    assert migrate("/**/" * 500_000 + "SELECT 1") == ["/**/" * 500_000 + "SELECT 1"]
    assert time.perf_counter() - started < 5.0


def test_run_migration_allows_commented_ddl_and_transaction_scoped_calls():
    sent = migrate(
        "/* add audit column */ ALTER TABLE users ADD COLUMN last_login_at TEXT; "
        "SELECT pg_advisory_xact_lock(1); SET LOCAL lock_timeout = '1s'"
    )
    assert len(sent) == 3
