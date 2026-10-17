# Production deployment

`deploy/production/docker-compose.yml` is the repository's only Compose
deployment profile. It uses persistent PostgreSQL volumes, private service
networking, non-root Python and Node containers, health/readiness probes, and
Caddy as the public TLS gateway. The former RAM-backed demo stack and stage
launchers have been removed so the default operational path cannot destroy
state accidentally.

## Prerequisites

- Docker Engine and Compose v2.
- A DNS record for the deployment hostname pointing at the host.
- TCP ports 80 and 443 available for Caddy certificate issuance/renewal.
- A secret manager or protected `.env` file. Never commit the production env.

## First deployment

```bash
cp deploy/production/.env.example deploy/production/.env
# Replace every placeholder and set PUBLIC_HOSTNAME to the real DNS name.
chmod 600 deploy/production/.env
make deploy-config
make up
```

`make deploy-config` runs the non-mutating preflight. It checks secret placeholders,
token length, HTTPS origin, env-file permissions, required Compose services,
and Compose interpolation without printing secret-expanded configuration.

Verify the public gateway and internal readiness:

```bash
curl --fail https://$PUBLIC_HOSTNAME/
curl --fail https://$PUBLIC_HOSTNAME/readyz
```

The first boot creates three cartridge databases and one durable audit
database. Run the seeder as an explicit operational action before enabling
traffic:

```bash
docker compose --env-file deploy/production/.env -f deploy/production/docker-compose.yml run --rm agent \
  python services/cartridges/seed_databases.py
```

The seeder is intentionally not part of the database container startup. This
prevents an application restart from silently destroying customer state.

## Operational requirements

1. **Secrets:** use a secret manager in place of `.env` for database passwords
   and `CHRONOS_API_TOKEN`. Rotate database credentials through a controlled
   migration, not by editing a running container.
2. **Backups:** enable PostgreSQL WAL archiving and scheduled base backups for
   both databases. The audit database is evidence, not a substitute for a
   tested backup/restore process.
3. **Observability:** collect JSON container logs, HTTP status/latency, database
   pool saturation, Z3 proof latency, UNSAT rates, and audit append failures.
   Alert on `/readyz` failures, repeated 503s, and any audit-chain error.
4. **Scaling:** keep one kernel process per stateful cartridge shard unless the
   deployment adds a shared DAG/event store. The current in-memory telemetry
   hub and DAG history are process-local; do not horizontally scale the kernel
   behind a load balancer without adding shared telemetry and sticky/session
   design.
5. **Security boundary:** keep PostgreSQL and the Python services on the
   private Compose network. Only Caddy publishes 80/443. Put an organization
   identity-aware proxy/WAF in front of Caddy for user authentication and
   authorization before exposing the control plane outside a trusted network.
6. **Updates:** build immutable image tags, run the contract, backend, live
   stack, and UI checks in CI, then roll forward with `make up`. Never bypass
   the production preflight or run ad-hoc destructive database commands.

## Readiness endpoints

| Service | Liveness | Readiness |
|---|---|---|
| Kernel | `/health` | `/readyz` |
| Z3 verifier | `/livez` | `/readyz` |
| Agent orchestrator | `/livez` | `/readyz` |
| UI gateway | `/` | Caddy upstream health |

Readiness is dependency-aware: the kernel checks all cartridge pools and the
durable audit database; the agent checks a cartridge database; the verifier
reports failed solver prewarming.
