"""PostgreSQL helpers for kernel tests (AGENTS.md §5: skip only when CHRONOS_PG_DSN is unreachable)."""
import asyncio
import os
import sys

import psycopg
import pytest

from cow_engine import DEFAULT_PG_DSN, database_name
from crypto_audit import DEFAULT_AUDIT_DSN

PG_DSN = (os.environ.get("CHRONOS_PG_DSN") or DEFAULT_PG_DSN).rstrip("/")
AUDIT_DSN = os.environ.get("CHRONOS_AUDIT_DSN") or DEFAULT_AUDIT_DSN
USER_COUNT = 50

# psycopg's async mode cannot run on Windows' default ProactorEventLoop.
LOOP_FACTORY = asyncio.SelectorEventLoop if sys.platform == "win32" else None

# Same tables as E3's seeder, in PostgreSQL types, with fewer users.
SCHEMAS = {
    "HEALTHCARE_FHIR": """
        DROP TABLE IF EXISTS patients, encounters, prescriptions CASCADE;
        CREATE TABLE patients(patient_id TEXT PRIMARY KEY, name TEXT, egfr_ml_min DOUBLE PRECISION, active_meds TEXT);
        CREATE TABLE encounters(encounter_id TEXT, patient_id TEXT, therapy_type TEXT, duration_weeks INT);
        CREATE TABLE prescriptions(id SERIAL PRIMARY KEY, patient_id TEXT, drug_name TEXT, daily_dose_mg INT,
                                   claim_submitted INT, conservative_therapy_weeks INT);
        INSERT INTO patients VALUES ('pat_402', 'John Doe', 24.0, 'Lisinopril');
        INSERT INTO encounters VALUES ('enc_108', 'pat_402', 'Physical Therapy', 6);
    """,
    "FINTECH_ESCROW": """
        DROP TABLE IF EXISTS treasury, vendors, transfers, cow_test_accounts CASCADE;
        CREATE TABLE treasury(account_id TEXT PRIMARY KEY, balance_usd DOUBLE PRECISION,
                              daily_spent_usd DOUBLE PRECISION, daily_limit_usd DOUBLE PRECISION);
        CREATE TABLE vendors(vendor_id TEXT PRIMARY KEY, name TEXT, iban TEXT, allowlisted INT,
                             sla_latency_ms DOUBLE PRECISION);
        CREATE TABLE transfers(id SERIAL PRIMARY KEY, vendor_id TEXT, amount_usd DOUBLE PRECISION, status TEXT);
        CREATE TABLE cow_test_accounts(id INT PRIMARY KEY, balance INT);
        INSERT INTO treasury VALUES ('acct_treasury', 50000.0, 4200.0, 5000.0);
        INSERT INTO vendors VALUES ('vnd_spoof', 'Acme Logistics (spoofed)', 'GB82WEST12345698765432', 0, 640.0);
        INSERT INTO vendors VALUES ('vnd_verified', 'Acme Logistics', 'DE89370400440532013000', 1, 85.0);
        INSERT INTO cow_test_accounts VALUES (1, 5000);
    """,
    "CLOUD_DEVOPS": f"""
        DROP TABLE IF EXISTS users, security_groups CASCADE;
        CREATE TABLE users(id INT PRIMARY KEY, email TEXT, role TEXT);
        CREATE TABLE security_groups(sg_id TEXT PRIMARY KEY, port INT, cidr_open_world INT);
        INSERT INTO security_groups VALUES ('sg_prod', 443, 0);
        INSERT INTO users SELECT g, 'user' || g || '@example.com', 'viewer' FROM generate_series(1, {USER_COUNT}) g;
    """,
}


def cartridge_dsn(cartridge_id: str) -> str:
    return f"{PG_DSN}/{database_name(cartridge_id)}"


def reset_databases() -> str:
    """Rebuild every cartridge database, or skip the test if PostgreSQL is not reachable."""
    try:
        psycopg.connect(cartridge_dsn("CLOUD_DEVOPS"), connect_timeout=2).close()
    except psycopg.OperationalError as exc:
        pytest.skip(f"PostgreSQL unreachable at {PG_DSN} (run `make db-up`): {exc}")
    for cartridge_id, script in SCHEMAS.items():
        with psycopg.connect(cartridge_dsn(cartridge_id), autocommit=True) as conn:
            conn.execute(script)
    reset_audit()  # ACTIVE branches cannot commit without an audit entry
    return PG_DSN


def reset_audit() -> str:
    """Empty the audit chain (DROP bypasses the append-only triggers), or skip if unreachable."""
    try:
        with psycopg.connect(AUDIT_DSN, autocommit=True, connect_timeout=2) as conn:
            conn.execute("DROP TABLE IF EXISTS audit_chain")
            conn.execute("DROP SCHEMA IF EXISTS audit_archive CASCADE")  # chains archived by resets
    except psycopg.OperationalError as exc:
        pytest.skip(f"audit PostgreSQL unreachable at {AUDIT_DSN} (run `make db-up`): {exc}")
    return AUDIT_DSN


def pg_query(cartridge_id: str, sql: str) -> list[tuple]:
    with psycopg.connect(cartridge_dsn(cartridge_id), autocommit=True) as conn:
        return conn.execute(sql).fetchall()


def run(coro):
    if LOOP_FACTORY is None:
        return asyncio.run(coro)
    with asyncio.Runner(loop_factory=LOOP_FACTORY) as runner:
        return runner.run(coro)
