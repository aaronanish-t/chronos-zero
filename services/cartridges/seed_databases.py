"""Deterministic seeder for the three cartridge databases.

Run: python services/cartridges/seed_databases.py
Wipes and recreates /dev/shm/chronos_{cartridge_id}.db for every cartridge.
"""
import os
import sqlite3
import sys
import tempfile
import time

# /dev/shm on Linux; Windows/macOS have no RAM disk there, so fall back to the temp dir.
DB_DIR = os.environ.get("CHRONOS_DB_DIR") or ("/dev/shm" if os.path.isdir("/dev/shm") else tempfile.gettempdir())

USER_COUNT = 15_420
ROLES = ("viewer", "editor", "admin")


def db_path(cartridge_id: str) -> str:
    return os.path.join(DB_DIR, f"chronos_{cartridge_id}.db")


def _fresh_conn(cartridge_id: str) -> sqlite3.Connection:
    path = db_path(cartridge_id)
    for suffix in ("", "-wal", "-shm"):
        try:
            os.remove(path + suffix)
        except FileNotFoundError:
            pass
    conn = sqlite3.connect(path)
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA synchronous=NORMAL;")
    return conn


def seed_healthcare(conn: sqlite3.Connection) -> None:
    conn.executescript("""
        CREATE TABLE patients(patient_id TEXT PRIMARY KEY, name TEXT, egfr_ml_min REAL, active_meds TEXT);
        CREATE TABLE encounters(encounter_id TEXT, patient_id TEXT, therapy_type TEXT, duration_weeks INT);
        CREATE TABLE prescriptions(id INTEGER PRIMARY KEY, patient_id TEXT, drug_name TEXT, daily_dose_mg INT,
                                   claim_submitted INT, conservative_therapy_weeks INT);
        INSERT INTO patients VALUES ('pat_402', 'John Doe', 24.0, 'Lisinopril');
        INSERT INTO encounters VALUES ('enc_108', 'pat_402', 'Physical Therapy', 6);
    """)


def seed_fintech(conn: sqlite3.Connection) -> None:
    conn.executescript("""
        CREATE TABLE treasury(account_id TEXT PRIMARY KEY, balance_usd REAL, daily_spent_usd REAL, daily_limit_usd REAL);
        CREATE TABLE vendors(vendor_id TEXT PRIMARY KEY, name TEXT, iban TEXT, allowlisted INT, sla_latency_ms REAL);
        CREATE TABLE transfers(id INTEGER PRIMARY KEY, vendor_id TEXT, amount_usd REAL, status TEXT);
        INSERT INTO treasury VALUES ('acct_treasury', 50000.0, 4200.0, 5000.0);
        INSERT INTO vendors VALUES ('vnd_spoof', 'Acme Logistics (spoofed)', 'GB82WEST12345698765432', 0, 640.0);
        INSERT INTO vendors VALUES ('vnd_verified', 'Acme Logistics', 'DE89370400440532013000', 1, 85.0);
    """)


def seed_devops(conn: sqlite3.Connection) -> None:
    conn.executescript("""
        CREATE TABLE users(id INTEGER PRIMARY KEY, email TEXT, role TEXT);
        CREATE TABLE security_groups(sg_id TEXT PRIMARY KEY, port INT, cidr_open_world INT);
        INSERT INTO security_groups VALUES ('sg_prod', 443, 0);
    """)
    conn.executemany(
        "INSERT INTO users VALUES (?, ?, ?)",
        ((i, f"user{i:05d}@example.com", ROLES[i % 3]) for i in range(1, USER_COUNT + 1)),
    )


SEEDERS = {
    "HEALTHCARE_FHIR": seed_healthcare,
    "FINTECH_ESCROW": seed_fintech,
    "CLOUD_DEVOPS": seed_devops,
}


def seed_all() -> float:
    """Reset every cartridge DB; returns elapsed milliseconds."""
    t0 = time.perf_counter_ns()
    for cartridge_id, seed in SEEDERS.items():
        conn = _fresh_conn(cartridge_id)
        try:
            with conn:
                seed(conn)
        finally:
            conn.close()
    return (time.perf_counter_ns() - t0) / 1_000_000.0


if __name__ == "__main__":
    try:
        ms = seed_all()
    except (sqlite3.Error, OSError) as exc:
        sys.exit(f"seed failed: {exc}")
    print(f"Seeded {len(SEEDERS)} cartridge DBs in {DB_DIR} in {ms:.1f} ms")
