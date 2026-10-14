import { AuditLogResponse, AuditEntry, TelemetryNode } from "../types/contracts";

const GENESIS_HASH = "0".repeat(64);
const UNIT_SEPARATOR = "\x1f";

/**
 * Compute SHA-256 hex string using browser Web Crypto API
 */
export async function sha256(text: string): Promise<string> {
  const encoder = new TextEncoder();
  const data = encoder.encode(text);
  const hashBuffer = await crypto.subtle.digest("SHA-256", data);
  const hashArray = Array.from(new Uint8Array(hashBuffer));
  return hashArray.map((b) => b.toString(16).padStart(2, "0")).join("");
}

/**
 * Match exact Python crypto_audit.py entry_hash logic
 */
export async function computeEntryHash(
  prevHash: string,
  traceId: string,
  smt2Dump: string,
  status: string,
  timestampNs: number | string
): Promise<string> {
  const payload = [prevHash, traceId, smt2Dump, status, String(timestampNs)].join(UNIT_SEPARATOR);
  return sha256(payload);
}

/**
 * Match exact Python crypto_audit.py merkle_root calculation
 */
export async function computeMerkleRoot(leaves: string[]): Promise<string> {
  if (leaves.length === 0) {
    return GENESIS_HASH;
  }
  let level = [...leaves];
  while (level.length > 1) {
    if (level.length % 2 === 1) {
      level.push(level[level.length - 1]);
    }
    const nextLevel: string[] = [];
    for (let i = 0; i < level.length; i += 2) {
      nextLevel.push(await sha256(level[i] + level[i + 1]));
    }
    level = nextLevel;
  }
  return level[0];
}

export interface AuditVerification {
  data: AuditLogResponse;
  /** Every entry_hash and prev_hash link recomputed in the browser. */
  chainVerified: boolean;
  /** Browser-computed Merkle root equals the kernel's. */
  rootMatches: boolean;
  /** This node's audit entry (matched by shadow branch), if it has one. */
  entry: AuditEntry | null;
  /** SHA-256(entry.smt2_dump) equals the node's sha256_proof_hash receipt. */
  receiptMatches: boolean | null;
}

/**
 * GET /v1/kernel/audit-log, then independently re-verify it with WebCrypto: rebuild every
 * entry hash and link, the Merkle root, and this node's receipt. Throws if the kernel is
 * unreachable; nothing is reported as verified without the kernel's real chain.
 */
export async function fetchAndVerifyAuditLog(node?: TelemetryNode | null): Promise<AuditVerification> {
  let res: Response;
  try {
    res = await fetch("/v1/kernel/audit-log", {
      headers: { Accept: "application/json" },
      signal: AbortSignal.timeout(3000),
    });
  } catch (e) {
    throw new Error(`kernel unreachable (${(e as Error).message})`);
  }
  if (!res.ok) throw new Error(`audit log unavailable (HTTP ${res.status})`);
  // timestamp_ns (~1.8e18) is beyond Number.MAX_SAFE_INTEGER: JSON.parse would round it and
  // every recomputed entry hash would mismatch. Keep those digits as strings.
  const raw = (await res.text()).replace(/"timestamp_ns"\s*:\s*(\d+)/g, '"timestamp_ns":"$1"');
  const data = JSON.parse(raw) as AuditLogResponse;

  let prev = GENESIS_HASH;
  let chainVerified = true;
  for (const [position, e] of data.entries.entries()) {
    const expected = await computeEntryHash(prev, e.trace_id, e.smt2_dump, e.status, e.timestamp_ns);
    if (e.index !== position || e.prev_hash !== prev || e.entry_hash !== expected) {
      chainVerified = false;
      break;
    }
    prev = e.entry_hash;
  }
  const rootMatches = (await computeMerkleRoot(data.entries.map((e) => e.entry_hash))) === data.merkle_root;

  const branchId = node?.id?.startsWith("node_") ? node.id.slice("node_".length) : null;
  const entry = branchId ? data.entries.find((e) => e.shadow_branch_id === branchId) ?? null : null;
  const receiptMatches =
    entry && node?.sha256_proof_hash ? (await sha256(entry.smt2_dump)) === node.sha256_proof_hash : null;

  return { data, chainVerified, rootMatches, entry, receiptMatches };
}
