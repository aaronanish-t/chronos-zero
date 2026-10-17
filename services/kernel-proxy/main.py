"""Entry point: python services/kernel-proxy/main.py (serves on :8000)."""

import asyncio
import os
import sys
from pathlib import Path

import uvicorn

REPO_ROOT = str(Path(__file__).resolve().parents[2])
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from services.runtime_config import validate_production_config
from interceptor import create_app

RUNTIME_CONFIG = validate_production_config()
app = create_app()

if __name__ == "__main__":
    server = uvicorn.Server(uvicorn.Config(app, host=RUNTIME_CONFIG.bind_host, port=RUNTIME_CONFIG.kernel_port))
    if sys.platform == "win32":
        # psycopg's async mode cannot run on Windows' default ProactorEventLoop.
        with asyncio.Runner(loop_factory=asyncio.SelectorEventLoop) as runner:
            runner.run(server.serve())
    else:
        server.run()
