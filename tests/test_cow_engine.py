import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "services" / "kernel-proxy"))

from cow_engine import CowEngine  # noqa: E402


def make_engine(tmp_path):
    db = tmp_path / "test.db"
    eng = CowEngine(str(db))
    eng.conn.execute("CREATE TABLE accounts (id INTEGER PRIMARY KEY, balance INTEGER)")
    eng.conn.execute("INSERT INTO accounts VALUES (1, 5000)")
    return eng


Q = "SELECT balance FROM accounts WHERE id = 1"


def balance(eng):
    return eng.conn.execute(Q).fetchone()[0]


def test_shadow_mutation_visible_then_rolled_back(tmp_path):
    eng = make_engine(tmp_path)
    bid, pre, post, _ = eng.fork_and_simulate(Q, "UPDATE accounts SET balance = balance - 4000 WHERE id = 1")
    assert pre["balance"] == 5000
    assert post["balance"] == 1000
    eng.resolve_branch(bid, commit=False)
    assert balance(eng) == 5000


def test_commit_persists_mutation(tmp_path):
    eng = make_engine(tmp_path)
    bid, _, _, _ = eng.fork_and_simulate(Q, "UPDATE accounts SET balance = balance - 400 WHERE id = 1")
    eng.resolve_branch(bid, commit=True)
    assert balance(eng) == 4600


def test_double_resolve_raises(tmp_path):
    eng = make_engine(tmp_path)
    bid, _, _, _ = eng.fork_and_simulate(Q, "UPDATE accounts SET balance = 0 WHERE id = 1")
    eng.resolve_branch(bid, commit=False)
    try:
        eng.resolve_branch(bid, commit=True)
    except KeyError:
        return
    raise AssertionError("expected KeyError on second resolve")
