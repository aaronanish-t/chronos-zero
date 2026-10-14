"""Entry point: python services/kernel-proxy/main.py (serves on :8000)."""

import asyncio
import sys

import uvicorn

from interceptor import create_app

app = create_app()

if __name__ == "__main__":
    server = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=8000))
    if sys.platform == "win32":
        # psycopg's async mode cannot run on Windows' default ProactorEventLoop.
        with asyncio.Runner(loop_factory=asyncio.SelectorEventLoop) as runner:
            runner.run(server.serve())
    else:
        server.run()
