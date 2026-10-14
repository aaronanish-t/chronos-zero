"""One-command stage launcher (`make stage`): kernel :8000, Z3 :8001, agent :8002, UI :3000.

Runs the whole demo offline (OFFLINE_MODE=1): the agent replays recorded tool calls when asked,
the Z3 policy compiler never calls an LLM, and every service binds 127.0.0.1. Expects Postgres
up (`make db-up`) and seeded (`make seed`). Ctrl+C stops everything.
Works on Linux (stage laptop) and Windows (dev).
"""

import os
import signal
import socket
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PY = sys.executable
NPX = "npx.cmd" if os.name == "nt" else "npx"

# --offset N moves every port by N (e.g. a second stack beside a teammate's on the same laptop).
OFFSET = int(sys.argv[sys.argv.index("--offset") + 1]) if "--offset" in sys.argv else 0
KERNEL, Z3, AGENT, UI = 8000 + OFFSET, 8001 + OFFSET, 8002 + OFFSET, 3000 + OFFSET

SERVICES = [
    ("kernel", [PY, "main.py"], ROOT / "services" / "kernel-proxy", KERNEL),
    ("z3", [PY, "server.py"], ROOT / "services" / "z3-verifier", Z3),
    ("agent", [PY, "orchestrator.py"], ROOT / "services" / "cartridges", AGENT),
    ("ui", [NPX, "next", "dev", "-p", str(UI)], ROOT / "services" / "multiverse-ui", UI),
]


def port_open(port: int) -> bool:
    with socket.socket() as s:
        s.settimeout(0.3)
        return s.connect_ex(("127.0.0.1", port)) == 0


def main() -> int:
    sys.stdout.reconfigure(line_buffering=True)  # progress lines appear immediately when piped
    env = {**os.environ, "OFFLINE_MODE": os.environ.get("OFFLINE_MODE", "1"), "PYTHONUNBUFFERED": "1",
           "NEXT_TELEMETRY_DISABLED": "1",
           "CHRONOS_KERNEL_PORT": str(KERNEL), "CHRONOS_Z3_PORT": str(Z3), "CHRONOS_AGENT_PORT": str(AGENT),
           "CHRONOS_Z3_URL": f"http://127.0.0.1:{Z3}/v1/z3/verify",
           "CHRONOS_KERNEL_URL": f"http://127.0.0.1:{KERNEL}",
           "CHRONOS_CORS_ORIGINS": f"http://localhost:{UI},http://127.0.0.1:{UI}",
            "CHRONOS_KERNEL_HTTP": f"http://127.0.0.1:{KERNEL}",
            "CHRONOS_KERNEL_POLICY_EVENT_URL": f"http://127.0.0.1:{KERNEL}/v1/kernel/telemetry/policy-compiled",
            "CHRONOS_Z3_HTTP": f"http://127.0.0.1:{Z3}",
           "CHRONOS_AGENT_HTTP": f"http://127.0.0.1:{AGENT}",
           "NEXT_PUBLIC_CHRONOS_WS_URL": f"ws://127.0.0.1:{KERNEL}/ws/telemetry"}
    try:
        import websockets  # noqa: F401  (uvicorn needs it to accept /ws/telemetry)
    except ImportError:
        print("missing the websockets package: pip install -r services/kernel-proxy/requirements.txt")
        return 1
    busy = [name for name, _, _, port in SERVICES if port_open(port)]
    if busy:
        print(f"ports already in use for: {', '.join(busy)} (stop the old stack first)")
        return 1

    procs = []
    for name, cmd, cwd, port in SERVICES:
        print(f"starting {name:6} on :{port}")
        procs.append((name, port, subprocess.Popen(cmd, cwd=cwd, env=env, stdin=subprocess.DEVNULL)))

    deadline = time.time() + 90
    pending = {name: port for name, port, _ in procs}
    while pending and time.time() < deadline:
        for name, port, proc in procs:
            if proc.poll() is not None:
                print(f"{name} exited with code {proc.returncode}; stopping the stack")
                return stop(procs, 1)
        for name, port in list(pending.items()):
            if port_open(port):
                print(f"  {name} ready on :{port}")
                del pending[name]
        time.sleep(0.5)
    if pending:
        print(f"timed out waiting for: {', '.join(pending)}")
        return stop(procs, 1)

    print("\nCHRONOS-ZERO stage is up (OFFLINE_MODE=%s). Open http://127.0.0.1:%d" % (env["OFFLINE_MODE"], UI))
    print("Pilot keys: 1/2/3 cartridge, Space run, B run without Chronos, R reset, S split screen. Ctrl+C to stop.")
    try:
        while all(proc.poll() is None for _, _, proc in procs):
            time.sleep(1)
        for name, port, proc in procs:
            if proc.poll() is not None:
                print(f"service '{name}' exited with code {proc.returncode}", flush=True)
        print("a service exited; stopping the stack", flush=True)
        return stop(procs, 1)
    except KeyboardInterrupt:
        return stop(procs, 0)


def stop(procs, code: int) -> int:
    for _, _, proc in procs:
        if proc.poll() is None:
            if os.name == "nt":
                subprocess.run(["taskkill", "/F", "/T", "/PID", str(proc.pid)], capture_output=True)
            else:
                proc.send_signal(signal.SIGINT)
    for _, _, proc in procs:
        try:
            proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            proc.kill()
    return code


if __name__ == "__main__":
    sys.exit(main())
