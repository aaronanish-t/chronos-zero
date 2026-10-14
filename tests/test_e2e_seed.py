import sys
from pathlib import Path

import psycopg
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "services" / "cartridges"))
import seed_databases as seed  # noqa: E402


@pytest.fixture(scope="module", autouse=True)
def postgres_up():
    try:
        psycopg.connect(seed.db_dsn("CLOUD_DEVOPS"), connect_timeout=2).close()
    except psycopg.OperationalError as exc:
        pytest.skip(f"PostgreSQL unreachable at CHRONOS_PG_DSN: {exc}")


def _one(cartridge_id, sql):
    with psycopg.connect(seed.db_dsn(cartridge_id)) as conn:
        return conn.execute(sql).fetchone()


def test_seed_is_fast_and_idempotent():
    seed.seed_all()
    assert seed.seed_all() < 500.0  # second run must also reset cleanly


def test_seed_values():
    seed.seed_all()
    assert _one("HEALTHCARE_FHIR", "SELECT name, egfr_ml_min, active_meds FROM patients WHERE patient_id='pat_402'") == ("John Doe", 24.0, "Lisinopril")
    assert _one("HEALTHCARE_FHIR", "SELECT therapy_type, duration_weeks FROM encounters WHERE encounter_id='enc_108'") == ("Physical Therapy", 6)
    assert _one("FINTECH_ESCROW", "SELECT balance_usd, daily_spent_usd, daily_limit_usd FROM treasury") == (50000.0, 4200.0, 5000.0)
    assert _one("FINTECH_ESCROW", "SELECT allowlisted, sla_latency_ms FROM vendors WHERE vendor_id='vnd_spoof'") == (0, 640.0)
    assert _one("FINTECH_ESCROW", "SELECT allowlisted, sla_latency_ms FROM vendors WHERE vendor_id='vnd_verified'") == (1, 85.0)
    assert _one("CLOUD_DEVOPS", "SELECT COUNT(*) FROM users") == (15_420,)
    assert _one("CLOUD_DEVOPS", "SELECT port, cidr_open_world FROM security_groups WHERE sg_id='sg_prod'") == (443, 0)


def test_identity_ids_for_kernel_inserts():
    seed.seed_all()
    with psycopg.connect(seed.db_dsn("FINTECH_ESCROW")) as conn:
        conn.execute("INSERT INTO transfers (vendor_id, amount_usd, status) VALUES ('vnd_verified', 1.0, 'SENT')")
        conn.rollback()
