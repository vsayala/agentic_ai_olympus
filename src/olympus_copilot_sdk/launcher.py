from __future__ import annotations

import os
import re
import secrets
import shutil
import socket
import subprocess  # nosec B404
import sys
import tempfile
import time
from pathlib import Path
from typing import BinaryIO

from streamlit.web import cli as streamlit_cli

ROOT = Path(__file__).parents[2]


def _available_port() -> int:
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        return int(listener.getsockname()[1])


def _diagnostics(log_output: BinaryIO) -> str:
    log_output.seek(0, os.SEEK_END)
    size = log_output.tell()
    log_output.seek(max(0, size - 4096))
    output = log_output.read().decode(errors="replace").strip()
    output = output.replace(str(ROOT), "<workspace>").replace(str(Path.home()), "~")
    return re.sub(
        r"(?i)\b(token|secret|password)(\s*[=:]\s*)\S+",
        r"\1\2<redacted>",
        output,
    )


def wait_for_server(process: subprocess.Popen[bytes], port: int, log_output: BinaryIO) -> None:
    deadline = time.monotonic() + 10
    while time.monotonic() < deadline:
        if process.poll() is not None:
            detail = _diagnostics(log_output)
            suffix = f" Recent diagnostics: {detail}" if detail else ""
            raise RuntimeError(f"Copilot CLI exited with code {process.returncode}.{suffix}")
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=0.2):
                return
        except OSError:
            time.sleep(0.05)
    raise RuntimeError("Timed out waiting for the Copilot CLI server.")


def stop_process(process: subprocess.Popen[bytes]) -> None:
    if process.poll() is not None:
        return
    process.terminate()
    try:
        process.wait(timeout=5)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait()


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
    with tempfile.TemporaryFile() as cli_log:
        cli_process = subprocess.Popen(  # nosec B603  # noqa: S603
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
            stdout=cli_log,
            stderr=subprocess.STDOUT,
        )

        try:
            wait_for_server(cli_process, port, cli_log)
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
            stop_process(cli_process)
