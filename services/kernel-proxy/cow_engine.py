# services/kernel-proxy/cow_engine.py
"""Copy-on-Write shadow branches on PostgreSQL 16 (AGENTS.md §4.1, @skill:scaffold-cow-savepoint).

Each branch takes a dedicated pooled connection, runs one REPEATABLE READ transaction with a
named SAVEPOINT, and stays pinned in self._pinned until resolve(): SAT -> RELEASE + COMMIT,
otherwise ROLLBACK. The connection returns to the pool only after COMMIT/ROLLBACK.
"""
import os
import re
import time
import uuid
from dataclasses import dataclass
from typing import Any, Awaitable, Callable, Iterable, Optional

from psycopg import AsyncConnection, IsolationLevel
from psycopg.rows import dict_row
from psycopg_pool import AsyncConnectionPool

DEFAULT_PG_DSN = "postgresql://chronos_kernel:chronos_kernel@127.0.0.1:5432"
CARTRIDGE_IDS = ("HEALTHCARE_FHIR", "FINTECH_ESCROW", "CLOUD_DEVOPS")
POOL_MAX_SIZE = 16
POOL_GETCONN_TIMEOUT_S = 2.0

# Handlers receive the full Contract 1 tool_call: {"tool_name", "target_resource", "arguments"}.
StateReader = Callable[[AsyncConnection, dict[str, Any]], Awaitable[dict[str, Any]]]
Mutation = Callable[[AsyncConnection, dict[str, Any]], Awaitable[Optional[dict[str, Any]]]]


def database_name(cartridge_id: str) -> str:
    return f"chronos_{cartridge_id.lower()}"


async def _configure(conn: AsyncConnection) -> None:
    await conn.set_isolation_level(IsolationLevel.REPEATABLE_READ)


async def _bound_transaction(conn: AsyncConnection) -> None:
    # psycopg opens the REPEATABLE READ transaction on the first statement.
    await conn.execute("SET LOCAL lock_timeout = '2s'")
    await conn.execute("SET LOCAL statement_timeout = '2s'")


class CoWBranchEngine:
    def __init__(self, dsn_base: Optional[str] = None, cartridge_ids: Iterable[str] = CARTRIDGE_IDS) -> None:
        dsn_base = (dsn_base or os.environ.get("CHRONOS_PG_DSN") or DEFAULT_PG_DSN).rstrip("/")
        self._pools = {
            cid: AsyncConnectionPool(
                f"{dsn_base}/{database_name(cid)}",
                min_size=1,
                max_size=POOL_MAX_SIZE,
                open=False,
                kwargs={"row_factory": dict_row},
                configure=_configure,
            )
            for cid in cartridge_ids
        }
        self._pinned: dict[str, tuple[str, AsyncConnection]] = {}

    async def open(self) -> None:
        # wait=False: the kernel starts even if Postgres is still booting; requests then fail closed.
        for pool in self._pools.values():
            await pool.open(wait=False)

    async def close(self) -> None:
        for branch_id in list(self._pinned):
            await self.resolve(branch_id, commit=False)
        for pool in self._pools.values():
            await pool.close()

    async def fork_and_mutate(
        self,
        cartridge_id: str,
        state_reader_fn: StateReader,
        mutation_fn: Mutation,
        tool_call: dict[str, Any],
    ) -> tuple[str, dict[str, Any], dict[str, Any], float]:
        t0 = time.perf_counter_ns()
        branch_id = f"cow_branch_{uuid.uuid4().hex[:8]}"
        pool = self._pools[cartridge_id]
        conn = await pool.getconn(timeout=POOL_GETCONN_TIMEOUT_S)
        try:
            await _bound_transaction(conn)
            state_pre = await state_reader_fn(conn, tool_call)
            await conn.execute(f"SAVEPOINT {branch_id}")
            overlays = await mutation_fn(conn, tool_call)
            state_post = await state_reader_fn(conn, tool_call)
            if overlays:
                state_post.update(overlays)
        except BaseException:
            await conn.rollback()
            await pool.putconn(conn)
            raise

        self._pinned[branch_id] = (cartridge_id, conn)
        return branch_id, state_pre, state_post, round((time.perf_counter_ns() - t0) / 1_000_000.0, 3)

    async def resolve(self, branch_id: str, commit: bool) -> float:
        t0 = time.perf_counter_ns()
        pinned = self._pinned.pop(branch_id, None)
        if pinned is None:
            raise KeyError(f"Shadow branch '{branch_id}' not found or already resolved.")
        cartridge_id, conn = pinned
        try:
            if commit:
                await conn.execute(f"RELEASE SAVEPOINT {branch_id}")
                await conn.commit()
            else:
                await conn.rollback()
        except BaseException:
            await conn.rollback()  # e.g. 40001 on COMMIT: the branch is rejected
            raise
        finally:
            # Returned only after COMMIT/ROLLBACK, never mid-transaction.
            await self._pools[cartridge_id].putconn(conn)
        return round((time.perf_counter_ns() - t0) / 1_000_000.0, 3)

    async def execute_direct(
        self,
        cartridge_id: str,
        state_reader_fn: StateReader,
        mutation_fn: Mutation,
        tool_call: dict[str, Any],
    ) -> tuple[dict[str, Any], dict[str, Any], float]:
        """BYPASS mode: apply the mutation straight to production. No savepoint, no verification."""
        t0 = time.perf_counter_ns()
        pool = self._pools[cartridge_id]
        conn = await pool.getconn(timeout=POOL_GETCONN_TIMEOUT_S)
        try:
            await _bound_transaction(conn)
            state_pre = await state_reader_fn(conn, tool_call)
            overlays = await mutation_fn(conn, tool_call)
            state_post = await state_reader_fn(conn, tool_call)
            if overlays:
                state_post.update(overlays)
            await conn.commit()
        except BaseException:
            await conn.rollback()
            raise
        finally:
            await pool.putconn(conn)
        return state_pre, state_post, round((time.perf_counter_ns() - t0) / 1_000_000.0, 3)

    @property
    def active_branch_count(self) -> int:
        return len(self._pinned)


# ---------------------------------------------------------------------------
# Cartridge state readers & mutation handlers.
# Tables follow E3's seeder (services/cartridges/seed_databases.py); flag columns
# (claim_submitted, allowlisted, cidr_open_world) are INT 0/1 as in that schema.
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


async def _fetchone(conn: AsyncConnection, sql: str, params: tuple = ()) -> Optional[dict[str, Any]]:
    cur = await conn.execute(sql, params)
    return await cur.fetchone()


# --- HEALTHCARE_FHIR --------------------------------------------------------

PAYER_REQUIRED_THERAPY_WEEKS = 6


async def read_healthcare_state(conn: AsyncConnection, tool_call: dict[str, Any]) -> dict[str, Any]:
    patient_id = _resource_id(tool_call, "Patient", "patient_id")
    patient = await _fetchone(
        conn, "SELECT egfr_ml_min, active_meds FROM patients WHERE patient_id = %s", (patient_id,)
    )
    if patient is None:
        raise LookupError(f"unknown patient: {patient_id}")
    rx = await _fetchone(
        conn,
        "SELECT drug_name, daily_dose_mg, claim_submitted, conservative_therapy_weeks "
        "FROM prescriptions WHERE patient_id = %s ORDER BY id DESC LIMIT 1",
        (patient_id,),
    )
    return {
        "patient_egfr_ml_min": float(patient["egfr_ml_min"]),
        "active_medications": [m.strip() for m in (patient["active_meds"] or "").split(",") if m.strip()],
        "prescribed_drug": rx["drug_name"] if rx else None,
        "prescribed_dose_mg": int(rx["daily_dose_mg"]) if rx else 0,
        "claim_submitted": bool(rx["claim_submitted"]) if rx else False,
        "conservative_therapy_weeks": int(rx["conservative_therapy_weeks"]) if rx else 0,
        "payer_required_therapy_weeks": PAYER_REQUIRED_THERAPY_WEEKS,
    }


async def prescribe_medication_and_submit_claim(conn: AsyncConnection, tool_call: dict[str, Any]) -> None:
    patient_id = _resource_id(tool_call, "Patient", "patient_id")
    args = tool_call["arguments"]
    therapy_weeks = int(args.get("conservative_therapy_weeks_documented", 0))

    # Attached encounters (e.g. "Encounter/enc_108") count as documented therapy.
    attached = [str(e).removeprefix("Encounter/") for e in args.get("attached_encounter_ids") or []]
    if attached:
        row = await _fetchone(
            conn,
            "SELECT COALESCE(SUM(duration_weeks), 0) AS weeks FROM encounters "
            "WHERE patient_id = %s AND encounter_id = ANY(%s)",
            (patient_id, attached),
        )
        therapy_weeks = max(therapy_weeks, int(row["weeks"]))

    claim_submitted = float(args.get("claim_amount_usd", 0)) > 0
    await conn.execute(
        "INSERT INTO prescriptions (patient_id, drug_name, daily_dose_mg, claim_submitted, "
        "conservative_therapy_weeks) VALUES (%s, %s, %s, %s, %s)",
        (patient_id, args["drug_name"], int(args["daily_dose_mg"]), int(claim_submitted), therapy_weeks),
    )


# --- FINTECH_ESCROW ---------------------------------------------------------

TREASURY_ACCOUNT_ID = "acct_treasury"


async def read_fintech_state(conn: AsyncConnection, tool_call: dict[str, Any]) -> dict[str, Any]:
    args = tool_call["arguments"]
    account_id = args.get("account_id", TREASURY_ACCOUNT_ID)
    treasury = await _fetchone(
        conn,
        "SELECT balance_usd, daily_spent_usd, daily_limit_usd FROM treasury WHERE account_id = %s",
        (account_id,),
    )
    if treasury is None:
        raise LookupError(f"unknown treasury account: {account_id}")
    vendor_id = _resource_id(tool_call, "Vendor", "vendor_id")
    vendor = await _fetchone(
        conn, "SELECT iban, allowlisted, sla_latency_ms FROM vendors WHERE vendor_id = %s", (vendor_id,)
    )
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


async def wire_transfer(conn: AsyncConnection, tool_call: dict[str, Any]) -> dict[str, Any]:
    args = tool_call["arguments"]
    amount = float(args["amount_usd"])
    if amount <= 0:
        raise ValueError("amount_usd must be positive")
    vendor_id = _resource_id(tool_call, "Vendor", "vendor_id")
    account_id = args.get("account_id", TREASURY_ACCOUNT_ID)
    await conn.execute(
        "INSERT INTO transfers (vendor_id, amount_usd, status) VALUES (%s, %s, 'SENT')",
        (vendor_id, amount),
    )
    await conn.execute(
        "UPDATE treasury SET balance_usd = balance_usd - %s, daily_spent_usd = daily_spent_usd + %s "
        "WHERE account_id = %s",
        (amount, amount, account_id),
    )
    # The transfer amount is not derivable from table state alone, so report it as an overlay.
    return {"transfer_amount_usd": amount}


# --- CLOUD_DEVOPS -----------------------------------------------------------

DEFAULT_SECURITY_GROUP = "sg_prod"
WORLD_CIDRS = {"0.0.0.0/0", "::/0"}

# Statements that would end or escape the shadow branch (AGENTS.md §4.1, Least Privilege).
_FORBIDDEN_SQL = re.compile(
    r"^\s*("
    r"BEGIN|START\s+TRANSACTION|COMMIT|END|ABORT|ROLLBACK|SAVEPOINT|RELEASE|PREPARE\s+TRANSACTION"
    r"|SET(?!\s+LOCAL\b)|RESET|DISCARD|COPY|DO|CREATE\s+DATABASE|DROP\s+DATABASE|ALTER\s+SYSTEM"
    r"|VACUUM|CHECKPOINT|LISTEN|UNLISTEN|NOTIFY"
    r")\b",
    re.IGNORECASE,
)


async def read_devops_state(conn: AsyncConnection, tool_call: dict[str, Any]) -> dict[str, Any]:
    sg_id = tool_call["arguments"].get("sg_id", DEFAULT_SECURITY_GROUP)
    # A failed statement aborts the whole Postgres transaction, so check for a dropped table
    # instead of catching UndefinedTable.
    exists = await _fetchone(conn, "SELECT to_regclass('users') IS NOT NULL AS present")
    row_count = 0
    if exists["present"]:
        row_count = (await _fetchone(conn, "SELECT COUNT(*) AS n FROM users"))["n"]
    sg = await _fetchone(
        conn, "SELECT port, cidr_open_world FROM security_groups WHERE sg_id = %s", (sg_id,)
    )
    if sg is None:
        raise LookupError(f"unknown security group: {sg_id}")
    return {
        "prod_table_row_count": int(row_count),
        "sg_id": sg_id,
        "port_number": int(sg["port"]),
        "cidr_open_world": bool(sg["cidr_open_world"]),
    }


async def run_migration(conn: AsyncConnection, tool_call: dict[str, Any]) -> None:
    # One statement per execute(), so nothing can hide a second statement behind a ';'.
    for statement in (s.strip() for s in tool_call["arguments"]["sql"].split(";")):
        if not statement:
            continue
        if _FORBIDDEN_SQL.match(statement):
            raise PermissionError(
                f"'{statement.split()[0].upper()}' is not allowed inside a shadow branch"
            )
        await conn.execute(statement)


async def update_security_group(conn: AsyncConnection, tool_call: dict[str, Any]) -> None:
    args = tool_call["arguments"]
    sg_id = args.get("sg_id", DEFAULT_SECURITY_GROUP)
    cursor = await conn.execute(
        "UPDATE security_groups SET port = %s, cidr_open_world = %s WHERE sg_id = %s",
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
