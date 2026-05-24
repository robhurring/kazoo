from __future__ import annotations

import json
import shlex

import pytest
from typer.testing import CliRunner

from kazoo.cli import app, state


@pytest.fixture(autouse=True)
def isolate_state(tmp_path, monkeypatch):
    """Each test gets a fresh XDG_DATA_HOME and a reset CLI state."""
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "xdg"))
    monkeypatch.delenv("KAZOO_DB", raising=False)
    state.db_name = None
    state.pretty = False
    yield


@pytest.fixture
def runner():
    return CliRunner()


@pytest.fixture
def run(runner):
    """Invoke `kazoo` with shlex-split args; return (result, parsed_json_or_none)."""

    def _run(cmd: str, input: str | None = None, expect_ok: bool = True):
        result = runner.invoke(app, shlex.split(cmd), input=input)
        if expect_ok and result.exit_code != 0:
            raise AssertionError(
                f"command failed (exit={result.exit_code}):\n"
                f"  cmd: kazoo {cmd}\n"
                f"  stdout: {result.stdout}\n"
            )
        out = result.stdout.strip()
        data = None
        if out:
            try:
                data = json.loads(out)
            except json.JSONDecodeError:
                data = None
        return result, data

    return _run
