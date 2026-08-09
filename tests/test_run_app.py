from __future__ import annotations

import io
import socket
import subprocess
from dataclasses import dataclass
from typing import cast

import pytest

from olympus_copilot_sdk import launcher as run_app


@dataclass
class FakeProcess:
    returncode: int | None = None
    terminate_calls: int = 0
    kill_calls: int = 0
    wait_calls: int = 0
    timeout_on_first_wait: bool = False

    def poll(self) -> int | None:
        return self.returncode

    def terminate(self) -> None:
        self.terminate_calls += 1

    def kill(self) -> None:
        self.kill_calls += 1
        self.returncode = -9

    def wait(self, timeout: float | None = None) -> int:
        del timeout
        self.wait_calls += 1
        if self.timeout_on_first_wait and self.wait_calls == 1:
            raise subprocess.TimeoutExpired("copilot", 5)
        self.returncode = 0 if self.returncode is None else self.returncode
        return self.returncode


def _process(value: FakeProcess) -> subprocess.Popen[bytes]:
    return cast(subprocess.Popen[bytes], value)


def _no_sleep(seconds: float) -> None:
    del seconds


def _unavailable_connection(*args: object, **kwargs: object) -> socket.socket:
    del args, kwargs
    raise OSError


def test_wait_for_server_reports_bounded_redacted_diagnostics() -> None:
    process = FakeProcess(returncode=2)
    log_output = io.BytesIO(
        f"workspace={run_app.ROOT} token=private-value\nstartup failed".encode()
    )

    with pytest.raises(RuntimeError) as raised:
        run_app.wait_for_server(_process(process), 1234, log_output)

    message = str(raised.value)
    assert "exited with code 2" in message
    assert "<workspace>" in message
    assert "token=<redacted>" in message
    assert "private-value" not in message


def test_wait_for_server_times_out(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monotonic_values = iter((0.0, 0.0, 11.0))
    monkeypatch.setattr(run_app.time, "monotonic", lambda: next(monotonic_values))
    monkeypatch.setattr(run_app.time, "sleep", _no_sleep)
    monkeypatch.setattr(
        run_app.socket,
        "create_connection",
        _unavailable_connection,
    )

    with pytest.raises(RuntimeError, match="Timed out"):
        run_app.wait_for_server(_process(FakeProcess()), 1234, io.BytesIO())


def test_stop_process_terminates_running_child() -> None:
    process = FakeProcess()

    run_app.stop_process(_process(process))

    assert (process.terminate_calls, process.kill_calls, process.wait_calls) == (1, 0, 1)


def test_stop_process_kills_child_after_timeout() -> None:
    process = FakeProcess(timeout_on_first_wait=True)

    run_app.stop_process(_process(process))

    assert (process.terminate_calls, process.kill_calls, process.wait_calls) == (1, 1, 2)


def test_stop_process_ignores_child_that_already_exited() -> None:
    process = FakeProcess(returncode=0)

    run_app.stop_process(_process(process))

    assert (process.terminate_calls, process.kill_calls, process.wait_calls) == (0, 0, 0)
