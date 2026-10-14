import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "services" / "cartridges"))
import seed_databases as seed  # noqa: E402


def _one(cartridge_id, sql):
    conn = sqlite3.connect(seed.db_path(cartridge_id))
    try:
        return conn.execute(sql).fetchone()
    finally:
        conn.close()


def test_seed_is_fast_and_idempotent():
    seed.seed_all()
    assert seed.seed_all() < 400.0  # second run must also wipe cleanly


def test_seed_values():
    seed.seed_all()
    assert _one("HEALTHCARE_FHIR", "PRAGMA journal_mode")[0] == "wal"
    assert _one("HEALTHCARE_FHIR", "SELECT name, egfr_ml_min, active_meds FROM patients WHERE patient_id='pat_402'") == ("John Doe", 24.0, "Lisinopril")
    assert _one("HEALTHCARE_FHIR", "SELECT therapy_type, duration_weeks FROM encounters WHERE encounter_id='enc_108'") == ("Physical Therapy", 6)
    assert _one("FINTECH_ESCROW", "SELECT balance_usd, daily_spent_usd, daily_limit_usd FROM treasury") == (50000.0, 4200.0, 5000.0)
    assert _one("FINTECH_ESCROW", "SELECT allowlisted, sla_latency_ms FROM vendors WHERE vendor_id='vnd_spoof'") == (0, 640.0)
    assert _one("FINTECH_ESCROW", "SELECT allowlisted, sla_latency_ms FROM vendors WHERE vendor_id='vnd_verified'") == (1, 85.0)
    assert _one("CLOUD_DEVOPS", "SELECT COUNT(*) FROM users") == (15_420,)
    assert _one("CLOUD_DEVOPS", "SELECT port, cidr_open_world FROM security_groups WHERE sg_id='sg_prod'") == (443, 0)
