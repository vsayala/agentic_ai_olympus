from __future__ import annotations

import os
import secrets
import shutil
import socket
import subprocess
import sys
import time
from pathlib import Path

from streamlit.web import cli as streamlit_cli

ROOT = Path(__file__).parent.resolve()


def _available_port() -> int:
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        return int(listener.getsockname()[1])


def _wait_for_server(process: subprocess.Popen[bytes], port: int) -> None:
    deadline = time.monotonic() + 10
    while time.monotonic() < deadline:
        if process.poll() is not None:
            raise RuntimeError(f"Copilot CLI exited with code {process.returncode}.")
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=0.2):
                return
        except OSError:
            time.sleep(0.05)
    raise RuntimeError("Timed out waiting for the Copilot CLI server.")


def main() -> int:
    cli_path = os.getenv("COPILOT_CLI_PATH") or shutil.which("copilot")
    if cli_path is None:
        raise RuntimeError(
            "GitHub Copilot CLI was not found. Install @github/copilot or set COPILOT_CLI_PATH."
        )

    port = _available_port()
    connection_token = secrets.token_urlsafe(32)
    cli_environment = os.environ.copy()
    cli_environment["COPILOT_CONNECTION_TOKEN"] = connection_token
    cli_process = subprocess.Popen(  # noqa: S603
        [
            cli_path,
            "--headless",
            "--no-auto-update",
            "--log-level",
            "info",
            "--port",
            str(port),
        ],
        cwd=ROOT,
        env=cli_environment,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )

    try:
        _wait_for_server(cli_process, port)
        os.environ["COPILOT_SERVER_URL"] = f"127.0.0.1:{port}"
        os.environ["COPILOT_CONNECTION_TOKEN"] = connection_token
        sys.argv = [
            "streamlit",
            "run",
            str(ROOT / "app.py"),
            "--server.headless",
            "true",
            "--server.port",
            os.getenv("STREAMLIT_PORT", "8501"),
        ]
        return int(streamlit_cli.main() or 0)
    finally:
        cli_process.terminate()
        try:
            cli_process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            cli_process.kill()
            cli_process.wait()


if __name__ == "__main__":
    raise SystemExit(main())
