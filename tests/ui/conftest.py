"""UI test fixtures and shared setup."""

import threading
import time

import pytest
import uvicorn

from smarthvac.dashboard import create_app


@pytest.fixture(scope="session")
def dashboard_url():
    """Start the FastAPI dashboard on a random port and yield its URL."""
    app = create_app()
    config = uvicorn.Config(app, host="127.0.0.1", port=0, log_level="warning")
    server = uvicorn.Server(config)
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()

    while not server.started:
        time.sleep(0.01)

    port = server.servers[0].sockets[0].getsockname()[1]
    url = f"http://127.0.0.1:{port}"

    yield url

    server.should_exit = True
    thread.join(timeout=5)
