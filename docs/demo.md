# Offline stage demo

`deploy/demo/` runs the full CHRONOS-ZERO demo on one laptop with **no internet**: the
kernel, Z3 verifier, agent orchestrator and UI on 127.0.0.1, against a RAM-backed
PostgreSQL. It is not a deployment; production is [docs/production.md](production.md).

| | Demo (`deploy/demo/`) | Production (`deploy/production/`) |
|---|---|---|
| Postgres | RAM (tmpfs), durability off, rebuilt by `make demo-seed` | Persistent volumes, normal durability |
| Network | 127.0.0.1 only | Private network + Caddy TLS on 80/443 |
| Needs DNS / internet | No | Yes (TLS certificates) |
| Credentials | Development defaults (rejected by production config) | Secrets from `.env` / secret manager |
| Agent tool calls | `OFFLINE_MODE=1` (recorded replay cache) | Live |

## Run

```bash
pip install -r services/kernel-proxy/requirements.txt -r services/z3-verifier/requirements.txt -r services/cartridges/requirements.txt
make ui-install      # once, with network
make demo-up         # RAM-backed Postgres + durable demo audit DB on 127.0.0.1:5432/5433
make demo-seed       # rebuild all three cartridge databases (< 0.5 s)
make stage           # kernel :8000, Z3 :8001, agent :8002, UI :3000; Ctrl+C stops all
```

Open http://127.0.0.1:3000. If those ports are taken: `python deploy/demo/stage.py --offset 100`
and open :3100.

Airplane-mode check (real kernel + Z3 + agent + Postgres; fails on any non-loopback
connection): `make demo-verify`.

## During the pitch

- Keys: **1/2/3** cartridge, **Space** run, **B** run without Chronos, **R** reset, **S** split screen.
- Plug in the laptop: on battery the CPU throttles and Z3 latency rises several-fold.
- Do one warm-up run (the first call opens the database pools).
- Press **R** between segments: the FinTech $5,000 daily cap allows two $400 heals.
- `make demo-down` stops the database; `make demo-reset` wipes and restarts it.
