"""Saga compensation ledger for non-SQL external APIs.

External APIs have no SAVEPOINT, so a speculative branch that calls one is undone by a
deterministic compensating action. Each forward mutation that a branch performs against an
API (or its OpenAPI stateful twin) is recorded with the id the API returned. If the branch is
rejected, compensations run newest-first; if it commits, the record is simply dropped.

Endpoints without a registered compensation are irreversible: callers must hold them until
the whole trajectory is proven SAT instead of executing them speculatively.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Optional

import httpx


@dataclass(frozen=True)
class Compensation:
    method: str
    path_template: str  # "{id}" is replaced with the id returned by the forward call
    id_field: str = "id"

    def path_for(self, resource_id: str) -> str:
        return self.path_template.replace("{id}", resource_id)


DEFAULT_COMPENSATIONS: dict[tuple[str, str], Compensation] = {
    ("POST", "/v1/wires"): Compensation("POST", "/v1/wires/{id}/reverse"),
    ("POST", "/v1/fhir/Claim"): Compensation("DELETE", "/v1/fhir/Claim/{id}"),
}

_SAFE_ID = re.compile(r"^[A-Za-z0-9._-]+$")


@dataclass(frozen=True)
class CompletedStep:
    forward_method: str
    forward_path: str
    resource_id: str
    compensation: Compensation


@dataclass
class CompensationResult:
    step: CompletedStep
    status_code: Optional[int]
    ok: bool
    error: Optional[str] = None


class CompensationFailed(RuntimeError):
    def __init__(self, branch_id: str, failures: list[CompensationResult]) -> None:
        self.failures = failures
        super().__init__(f"{len(failures)} compensation(s) failed for {branch_id}")


@dataclass
class SagaLedger:
    registry: dict[tuple[str, str], Compensation] = field(default_factory=lambda: dict(DEFAULT_COMPENSATIONS))
    _steps: dict[str, list[CompletedStep]] = field(default_factory=dict)

    def is_reversible(self, method: str, path: str) -> bool:
        return (method.upper(), path) in self.registry

    def record(self, branch_id: str, method: str, path: str, response_json: dict[str, Any]) -> CompletedStep:
        """Record a forward mutation that already succeeded inside branch_id."""
        compensation = self.registry.get((method.upper(), path))
        if compensation is None:
            raise LookupError(f"{method.upper()} {path} has no compensation; hold it until SAT instead")
        resource_id = str(response_json.get(compensation.id_field, ""))
        if not _SAFE_ID.match(resource_id):
            raise ValueError(f"forward response has no usable '{compensation.id_field}': {resource_id!r}")
        step = CompletedStep(method.upper(), path, resource_id, compensation)
        self._steps.setdefault(branch_id, []).append(step)
        return step

    def pending(self, branch_id: str) -> list[CompletedStep]:
        return list(self._steps.get(branch_id, []))

    def commit(self, branch_id: str) -> None:
        """Branch proved SAT: its forward calls stand, nothing to undo."""
        self._steps.pop(branch_id, None)

    async def compensate(self, branch_id: str, client: httpx.AsyncClient, base_url: str) -> list[CompensationResult]:
        """Branch rejected: run every compensation newest-first.

        All compensations are attempted even if one fails; failures are then raised together so
        the caller can alert, because the external system is left partially changed.
        """
        results: list[CompensationResult] = []
        for step in reversed(self._steps.pop(branch_id, [])):
            url = base_url.rstrip("/") + step.compensation.path_for(step.resource_id)
            try:
                response = await client.request(step.compensation.method, url)
                results.append(CompensationResult(step, response.status_code, response.is_success))
            except httpx.HTTPError as exc:
                results.append(CompensationResult(step, None, False, str(exc)))
        failures = [r for r in results if not r.ok]
        if failures:
            raise CompensationFailed(branch_id, failures)
        return results
