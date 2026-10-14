# services/kernel-proxy/cow_engine.py
import os
import re
import sqlite3
import tempfile
import threading
import time
import uuid
from dataclasses import dataclass
from typing import Any, Callable, Optional

# /dev/shm on Linux; CHRONOS_DB_DIR overrides; system temp dir elsewhere (e.g. Windows dev boxes).
SHM_DIR = os.environ.get("CHRONOS_DB_DIR") or (
    "/dev/shm" if os.path.exists("/dev/shm") else tempfile.gettempdir()
)

# Handlers receive the full Contract 1 tool_call: {"tool_name", "target_resource", "arguments"}.
StateReader = Callable[[sqlite3.Connection, dict[str, Any]], dict[str, Any]]
Mutation = Callable[[sqlite3.Connection, dict[str, Any]], Optional[dict[str, Any]]]


class CoWBranchEngine:
    """
    Per-branch isolated SQLite WAL Savepoint manager.
    Conforms strictly to AGENTS.md Section 4.1:
    - Separate connection opened per shadow branch.
    - Pinned in memory until Z3 returns SAT or UNSAT.
    - Explicitly closed once committed or rolled back.
    """

    def __init__(self) -> None:
        self._pinned: dict[str, sqlite3.Connection] = {}
        self._lock = threading.Lock()

    @staticmethod
    def get_db_path(cartridge_id: str) -> str:
        return os.path.join(SHM_DIR, f"chronos_{cartridge_id}.db")

    def _open_branch_connection(self, cartridge_id: str) -> sqlite3.Connection:
        db_path = self.get_db_path(cartridge_id)
        conn = sqlite3.connect(
            db_path,
            timeout=5.0,
            isolation_level=None,  # Autocommit mode so manual SAVEPOINT controls tx boundary
            check_same_thread=False,
        )
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("PRAGMA synchronous=NORMAL;")
        conn.execute("PRAGMA temp_store=MEMORY;")
        return conn

    def fork_and_mutate(
        self,
        cartridge_id: str,
        state_reader_fn: StateReader,
        mutation_fn: Mutation,
        tool_args: dict[str, Any],
    ) -> tuple[str, dict[str, Any], dict[str, Any], float]:
        t0 = time.perf_counter_ns()
        branch_id = f"cow_branch_{uuid.uuid4().hex[:8]}"
        conn = self._open_branch_connection(cartridge_id)

        try:
            # 1. Read pre-mutation state snapshot
            state_pre = state_reader_fn(conn, tool_args)

            # 2. Fork isolated Copy-on-Write savepoint on this dedicated connection
            conn.execute(f"SAVEPOINT {branch_id};")

            # 3. Apply speculative tool mutation inside the savepoint
            mutation_overlays = mutation_fn(conn, tool_args)

            # 4. Read post-mutation shadow state & merge any transient mutation overlays
            state_post_shadow = state_reader_fn(conn, tool_args)
            if mutation_overlays:
                state_post_shadow.update(mutation_overlays)

        except Exception:
            try:
                conn.execute(f"ROLLBACK TO SAVEPOINT {branch_id};")
                conn.execute(f"RELEASE SAVEPOINT {branch_id};")
            except sqlite3.Error:
                pass
            conn.close()
            raise

        with self._lock:
            self._pinned[branch_id] = conn

        fork_latency_ms = round((time.perf_counter_ns() - t0) / 1_000_000.0, 3)
        return branch_id, state_pre, state_post_shadow, fork_latency_ms

    def resolve(self, branch_id: str, commit: bool) -> float:
        """
        Commits (RELEASE SAVEPOINT) or rolls back (ROLLBACK TO SAVEPOINT)
        and unconditionally closes the branch's dedicated connection.
        """
        t0 = time.perf_counter_ns()
        with self._lock:
            conn = self._pinned.pop(branch_id, None)

        if conn is None:
            raise KeyError(f"Shadow branch '{branch_id}' not found or already resolved.")

        try:
            if commit:
                conn.execute(f"RELEASE SAVEPOINT {branch_id};")
            else:
                conn.execute(f"ROLLBACK TO SAVEPOINT {branch_id};")
                conn.execute(f"RELEASE SAVEPOINT {branch_id};")
        finally:
            conn.close()

        return round((time.perf_counter_ns() - t0) / 1_000_000.0, 3)

    def execute_direct(
        self,
        cartridge_id: str,
        state_reader_fn: StateReader,
        mutation_fn: Mutation,
        tool_args: dict[str, Any],
    ) -> tuple[dict[str, Any], dict[str, Any], float]:
        """BYPASS mode: apply the mutation straight to production. No savepoint, no verification."""
        t0 = time.perf_counter_ns()
        conn = self._open_branch_connection(cartridge_id)
        try:
            state_pre = state_reader_fn(conn, tool_args)
            conn.execute("BEGIN IMMEDIATE;")
            try:
                mutation_overlays = mutation_fn(conn, tool_args)
                state_post = state_reader_fn(conn, tool_args)
                if mutation_overlays:
                    state_post.update(mutation_overlays)
                conn.execute("COMMIT;")
            except Exception:
                conn.execute("ROLLBACK;")
                raise
        finally:
            conn.close()
        return state_pre, state_post, round((time.perf_counter_ns() - t0) / 1_000_000.0, 3)

    @property
    def active_branch_count(self) -> int:
        with self._lock:
            return len(self._pinned)


# ---------------------------------------------------------------------------
# Cartridge state readers & mutation handlers.
# Table layouts follow services/cartridges/seed_databases.py (E3).
# State keys follow Contract 2 and the keys read by the Z3 verifier (E2).
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class CartridgeToolHandler:
    state_reader: StateReader
    mutation: Mutation


def _resource_id(tool_call: dict[str, Any], prefix: str, arg_key: str) -> str:
    """Resolve an entity id from an explicit argument or a 'Prefix/id' target_resource."""
    explicit = tool_call["arguments"].get(arg_key)
    if explicit:
        return str(explicit)
    resource = tool_call["target_resource"]
    return resource.split("/", 1)[1] if resource.startswith(f"{prefix}/") else resource


# --- HEALTHCARE_FHIR --------------------------------------------------------

PAYER_REQUIRED_THERAPY_WEEKS = 6


def read_healthcare_state(conn: sqlite3.Connection, tool_call: dict[str, Any]) -> dict[str, Any]:
    patient_id = _resource_id(tool_call, "Patient", "patient_id")
    patient = conn.execute(
        "SELECT egfr_ml_min, active_meds FROM patients WHERE patient_id = ?", (patient_id,)
    ).fetchone()
    if patient is None:
        raise LookupError(f"unknown patient: {patient_id}")
    rx = conn.execute(
        "SELECT drug_name, daily_dose_mg, claim_submitted, conservative_therapy_weeks "
        "FROM prescriptions WHERE patient_id = ? ORDER BY id DESC LIMIT 1",
        (patient_id,),
    ).fetchone()
    return {
        "patient_egfr_ml_min": float(patient["egfr_ml_min"]),
        "active_medications": [m.strip() for m in (patient["active_meds"] or "").split(",") if m.strip()],
        "prescribed_drug": rx["drug_name"] if rx else None,
        "prescribed_dose_mg": int(rx["daily_dose_mg"]) if rx else 0,
        "claim_submitted": bool(rx["claim_submitted"]) if rx else False,
        "conservative_therapy_weeks": int(rx["conservative_therapy_weeks"]) if rx else 0,
        "payer_required_therapy_weeks": PAYER_REQUIRED_THERAPY_WEEKS,
    }


def prescribe_medication_and_submit_claim(conn: sqlite3.Connection, tool_call: dict[str, Any]) -> None:
    patient_id = _resource_id(tool_call, "Patient", "patient_id")
    args = tool_call["arguments"]
    therapy_weeks = int(args.get("conservative_therapy_weeks_documented", 0))

    # Attached encounters (e.g. "Encounter/enc_108") count as documented therapy.
    attached = [str(e).removeprefix("Encounter/") for e in args.get("attached_encounter_ids") or []]
    if attached:
        placeholders = ",".join("?" * len(attached))
        row = conn.execute(
            "SELECT COALESCE(SUM(duration_weeks), 0) FROM encounters "
            f"WHERE patient_id = ? AND encounter_id IN ({placeholders})",
            (patient_id, *attached),
        ).fetchone()
        therapy_weeks = max(therapy_weeks, int(row[0]))

    claim_submitted = float(args.get("claim_amount_usd", 0)) > 0
    conn.execute(
        "INSERT INTO prescriptions (patient_id, drug_name, daily_dose_mg, claim_submitted, "
        "conservative_therapy_weeks) VALUES (?, ?, ?, ?, ?)",
        (patient_id, args["drug_name"], int(args["daily_dose_mg"]), int(claim_submitted), therapy_weeks),
    )


# --- FINTECH_ESCROW ---------------------------------------------------------

TREASURY_ACCOUNT_ID = "acct_treasury"


def read_fintech_state(conn: sqlite3.Connection, tool_call: dict[str, Any]) -> dict[str, Any]:
    args = tool_call["arguments"]
    account_id = args.get("account_id", TREASURY_ACCOUNT_ID)
    treasury = conn.execute(
        "SELECT balance_usd, daily_spent_usd, daily_limit_usd FROM treasury WHERE account_id = ?",
        (account_id,),
    ).fetchone()
    if treasury is None:
        raise LookupError(f"unknown treasury account: {account_id}")
    vendor_id = _resource_id(tool_call, "Vendor", "vendor_id")
    vendor = conn.execute(
        "SELECT iban, allowlisted, sla_latency_ms FROM vendors WHERE vendor_id = ?", (vendor_id,)
    ).fetchone()
    if vendor is None:
        raise LookupError(f"unknown vendor: {vendor_id}")

    # A payout IBAN that differs from the vendor's registered one is never allowlisted.
    payout_iban = args.get("iban") or vendor["iban"]
    return {
        "treasury_balance_usd": float(treasury["balance_usd"]),
        "daily_escrow_spent_usd": float(treasury["daily_spent_usd"]),
        "daily_escrow_limit_usd": float(treasury["daily_limit_usd"]),
        "vendor_id": vendor_id,
        "payout_iban": payout_iban,
        "vendor_latency_ms": float(vendor["sla_latency_ms"]),
        "iban_allowlisted": bool(vendor["allowlisted"]) and payout_iban == vendor["iban"],
        "transfer_amount_usd": 0.0,
    }


def wire_transfer(conn: sqlite3.Connection, tool_call: dict[str, Any]) -> dict[str, Any]:
    args = tool_call["arguments"]
    amount = float(args["amount_usd"])
    if amount <= 0:
        raise ValueError("amount_usd must be positive")
    vendor_id = _resource_id(tool_call, "Vendor", "vendor_id")
    account_id = args.get("account_id", TREASURY_ACCOUNT_ID)
    conn.execute(
        "INSERT INTO transfers (vendor_id, amount_usd, status) VALUES (?, ?, 'SENT')",
        (vendor_id, amount),
    )
    conn.execute(
        "UPDATE treasury SET balance_usd = balance_usd - ?, daily_spent_usd = daily_spent_usd + ? "
        "WHERE account_id = ?",
        (amount, amount, account_id),
    )
    # The transfer amount is not derivable from table state alone, so report it as an overlay.
    return {"transfer_amount_usd": amount}


# --- CLOUD_DEVOPS -----------------------------------------------------------

DEFAULT_SECURITY_GROUP = "sg_prod"
WORLD_CIDRS = {"0.0.0.0/0", "::/0"}

# Statements that would end or escape the shadow savepoint (and so commit to production unverified).
_FORBIDDEN_SQL = re.compile(
    r"^\s*(BEGIN|COMMIT|END|ROLLBACK|SAVEPOINT|RELEASE|ATTACH|DETACH|VACUUM|PRAGMA)\b", re.IGNORECASE
)
_DROP_CASCADE = re.compile(r"\s+CASCADE\s*$", re.IGNORECASE)


def read_devops_state(conn: sqlite3.Connection, tool_call: dict[str, Any]) -> dict[str, Any]:
    sg_id = tool_call["arguments"].get("sg_id", DEFAULT_SECURITY_GROUP)
    try:
        row_count = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
    except sqlite3.OperationalError as exc:
        if "no such table" not in str(exc):
            raise
        row_count = 0  # table was dropped
    sg = conn.execute(
        "SELECT port, cidr_open_world FROM security_groups WHERE sg_id = ?", (sg_id,)
    ).fetchone()
    if sg is None:
        raise LookupError(f"unknown security group: {sg_id}")
    return {
        "prod_table_row_count": int(row_count),
        "sg_id": sg_id,
        "port_number": int(sg["port"]),
        "cidr_open_world": bool(sg["cidr_open_world"]),
    }


def run_migration(conn: sqlite3.Connection, tool_call: dict[str, Any]) -> None:
    # conn.executescript() is not usable here: it COMMITs first, which would release the savepoint.
    for statement in (s.strip() for s in tool_call["arguments"]["sql"].split(";")):
        if not statement:
            continue
        if _FORBIDDEN_SQL.match(statement):
            raise PermissionError(
                f"'{statement.split()[0].upper()}' is not allowed inside a shadow branch"
            )
        # The mock emulates production Postgres; SQLite has no DROP TABLE ... CASCADE.
        if statement.upper().startswith("DROP TABLE"):
            statement = _DROP_CASCADE.sub("", statement)
        conn.execute(statement)


def update_security_group(conn: sqlite3.Connection, tool_call: dict[str, Any]) -> None:
    args = tool_call["arguments"]
    sg_id = args.get("sg_id", DEFAULT_SECURITY_GROUP)
    cursor = conn.execute(
        "UPDATE security_groups SET port = ?, cidr_open_world = ? WHERE sg_id = ?",
        (int(args["port"]), int(str(args.get("cidr", "")) in WORLD_CIDRS), sg_id),
    )
    if cursor.rowcount == 0:
        raise LookupError(f"unknown security group: {sg_id}")


CARTRIDGE_HANDLERS: dict[tuple[str, str], CartridgeToolHandler] = {
    ("HEALTHCARE_FHIR", "prescribe_medication_and_submit_claim"): CartridgeToolHandler(
        read_healthcare_state, prescribe_medication_and_submit_claim
    ),
    ("FINTECH_ESCROW", "wire_transfer"): CartridgeToolHandler(read_fintech_state, wire_transfer),
    ("CLOUD_DEVOPS", "run_migration"): CartridgeToolHandler(read_devops_state, run_migration),
    ("CLOUD_DEVOPS", "update_security_group"): CartridgeToolHandler(
        read_devops_state, update_security_group
    ),
}
