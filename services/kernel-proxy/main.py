"""Entry point: python services/kernel-proxy/main.py (serves on :8000)."""

import uvicorn

from interceptor import create_app

app = create_app()

if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8000)
