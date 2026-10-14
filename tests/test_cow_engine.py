import sqlite3

import pytest

import cow_engine
from cow_engine import CoWBranchEngine

CARTRIDGE = "FINTECH_ESCROW"


@pytest.fixture
def engine(tmp_path, monkeypatch):
    monkeypatch.setattr(cow_engine, "SHM_DIR", str(tmp_path))
    eng = CoWBranchEngine()
    conn = sqlite3.connect(eng.get_db_path(CARTRIDGE))
    conn.execute("CREATE TABLE accounts (id INTEGER PRIMARY KEY, balance INTEGER)")
    conn.execute("INSERT INTO accounts VALUES (1, 5000)")
    conn.commit()
    conn.close()
    return eng


def read_balance(conn, _args):
    return {"balance": conn.execute("SELECT balance FROM accounts WHERE id = 1").fetchone()[0]}


def debit(conn, args):
    conn.execute("UPDATE accounts SET balance = balance - ? WHERE id = 1", (args["amount"],))
    return {}


def committed_balance(eng):
    conn = sqlite3.connect(eng.get_db_path(CARTRIDGE))
    try:
        return conn.execute("SELECT balance FROM accounts WHERE id = 1").fetchone()[0]
    finally:
        conn.close()


def test_shadow_mutation_visible_then_rolled_back(engine):
    bid, pre, post, _ = engine.fork_and_mutate(CARTRIDGE, read_balance, debit, {"amount": 4000})
    assert pre["balance"] == 5000
    assert post["balance"] == 1000
    engine.resolve(bid, commit=False)
    assert committed_balance(engine) == 5000
    assert engine.active_branch_count == 0


def test_commit_persists_mutation(engine):
    bid, _, _, _ = engine.fork_and_mutate(CARTRIDGE, read_balance, debit, {"amount": 400})
    engine.resolve(bid, commit=True)
    assert committed_balance(engine) == 4600


def test_uncommitted_branch_invisible_to_other_connections(engine):
    bid, _, _, _ = engine.fork_and_mutate(CARTRIDGE, read_balance, debit, {"amount": 4000})
    assert committed_balance(engine) == 5000
    engine.resolve(bid, commit=False)


def test_mutation_overlay_merged_into_post_state(engine):
    def overlay(conn, args):
        debit(conn, args)
        return {"iban_allowlisted": False}

    bid, _, post, _ = engine.fork_and_mutate(CARTRIDGE, read_balance, overlay, {"amount": 1})
    assert post == {"balance": 4999, "iban_allowlisted": False}
    engine.resolve(bid, commit=False)


def test_mutation_failure_rolls_back_and_unpins(engine):
    def boom(conn, args):
        debit(conn, args)
        raise RuntimeError("tool failed")

    with pytest.raises(RuntimeError):
        engine.fork_and_mutate(CARTRIDGE, read_balance, boom, {"amount": 4000})
    assert engine.active_branch_count == 0
    assert committed_balance(engine) == 5000


def test_double_resolve_raises(engine):
    bid, _, _, _ = engine.fork_and_mutate(CARTRIDGE, read_balance, debit, {"amount": 1})
    engine.resolve(bid, commit=False)
    with pytest.raises(KeyError):
        engine.resolve(bid, commit=True)
