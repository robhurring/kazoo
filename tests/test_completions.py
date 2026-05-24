from __future__ import annotations

import pytest


@pytest.mark.parametrize("shell", ["bash", "zsh", "fish"])
def test_completions_emit_script(runner, shell):
    from kazoo.cli import app

    result = runner.invoke(app, ["completions", shell])
    assert result.exit_code == 0
    assert result.stdout.strip(), "expected a non-empty completion script"
    # Each shell's emitted script mentions _KAZOO_COMPLETE somewhere
    assert "_KAZOO_COMPLETE" in result.stdout


def test_completions_unknown_shell(run):
    result, data = run("completions powershell", expect_ok=False)
    assert result.exit_code != 0
    assert "unknown shell" in data["error"]
