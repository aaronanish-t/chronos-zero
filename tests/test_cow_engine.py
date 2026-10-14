import pytest

from cow_engine import CoWBranchEngine
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
