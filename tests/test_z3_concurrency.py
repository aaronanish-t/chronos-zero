"""Z3's global context is not thread-safe; the verifier must serialize solver work.

FastAPI runs the sync /v1/z3/verify and /v1/z3/compile-policy routes on worker threads, so
overlapping requests (split comparison, benchmark, a policy compile during a run) used to
crash the process natively. The load runs in a subprocess so a regression fails this test
instead of killing pytest.
"""

import subprocess
import sys
import textwrap
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]

LOAD = textwrap.dedent(
    """
    import sys, threading
    sys.path.insert(0, {verifier!r})
    sys.path.insert(0, {root!r})
    from fastapi.testclient import TestClient
    import server

    diff = {{
        "trace_id": "tr_conc", "shadow_branch_id": "cow_branch_conc", "cartridge_id": "HEALTHCARE_FHIR",
        "cow_fork_latency_ms": 1.0, "state_pre": {{}},
        "state_post_shadow": {{"patient_egfr_ml_min": 24.0, "prescribed_drug": "Metformin",
                               "prescribed_dose_mg": 2500, "claim_submitted": True,
                               "conservative_therapy_weeks": 2}},
    }}
    bad = []
    with TestClient(server.app) as client:
        def work(n):
            for i in range(60):
                if n == 0 and i % 10 == 0:
                    r = client.post("/v1/z3/compile-policy", json={{
                        "cartridge_id": "CLOUD_DEVOPS", "rule_id": "INV_CONC_01_SSH",
                        "natural_language_rule": "SSH port 22 must never be open to the internet."}})
                else:
                    r = client.post("/v1/z3/verify", json=diff)
                    if r.status_code != 200 or r.json()["status"] != "UNSAT":
                        bad.append(r.status_code)
        threads = [threading.Thread(target=work, args=(n,)) for n in range(8)]
        [t.start() for t in threads]
        [t.join() for t in threads]
    print("BAD", len(bad))
    sys.exit(1 if bad else 0)
    """
).format(verifier=str(REPO_ROOT / "services" / "z3-verifier"), root=str(REPO_ROOT))


def test_concurrent_verify_and_compile_do_not_crash_the_prover():
    proc = subprocess.run([sys.executable, "-c", LOAD], capture_output=True, text=True, timeout=240)
    assert proc.returncode == 0, f"exit {proc.returncode}\n{proc.stdout[-2000:]}\n{proc.stderr[-2000:]}"
    assert "BAD 0" in proc.stdout
