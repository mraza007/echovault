"""Smoke tests for the curl-friendly installer."""

import os
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
INSTALLER = ROOT / "install.sh"


def test_installer_has_valid_posix_shell_syntax():
    result = subprocess.run(
        ["sh", "-n", str(INSTALLER)],
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr


def test_installer_help_does_not_install():
    result = subprocess.run(
        ["sh", str(INSTALLER), "--help"],
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0
    assert "--agent AGENT" in result.stdout
    assert "default: main" in result.stdout


def test_installer_uses_uv_and_explicit_git_source(tmp_path):
    fake_bin = tmp_path / "bin"
    home = tmp_path / "home"
    args_file = tmp_path / "uv-args"
    fake_bin.mkdir()
    home.mkdir()

    uv = fake_bin / "uv"
    uv.write_text(
        "#!/bin/sh\n"
        'printf "%s\\n" "$@" > "$UV_ARGS_FILE"\n'
    )
    uv.chmod(0o755)

    git = fake_bin / "git"
    git.write_text("#!/bin/sh\nexit 0\n")
    git.chmod(0o755)

    env = os.environ.copy()
    env.update({
        "HOME": str(home),
        "PATH": f"{fake_bin}:/usr/bin:/bin",
        "UV_ARGS_FILE": str(args_file),
    })
    result = subprocess.run(
        ["sh", str(INSTALLER), "--no-setup"],
        capture_output=True,
        text=True,
        env=env,
    )

    assert result.returncode == 0, result.stderr
    assert args_file.read_text().splitlines() == [
        "tool",
        "install",
        "--force",
        "git+https://github.com/mraza007/echovault.git@main",
    ]
    assert "Installed with uv." in result.stdout


def test_installer_rejects_unknown_agent():
    result = subprocess.run(
        ["sh", str(INSTALLER), "--agent", "unknown"],
        capture_output=True,
        text=True,
    )

    assert result.returncode != 0
    assert "unsupported agent" in result.stderr


def test_installer_initializes_and_configures_requested_agent(tmp_path):
    fake_bin = tmp_path / "bin"
    home = tmp_path / "home"
    calls_file = tmp_path / "memory-calls"
    fake_bin.mkdir()
    (home / ".local" / "bin").mkdir(parents=True)

    uv = fake_bin / "uv"
    uv.write_text("#!/bin/sh\nexit 0\n")
    uv.chmod(0o755)

    git = fake_bin / "git"
    git.write_text("#!/bin/sh\nexit 0\n")
    git.chmod(0o755)

    memory = home / ".local" / "bin" / "memory"
    memory.write_text(
        "#!/bin/sh\n"
        'if [ "${1:-}" = "--version" ]; then\n'
        '  echo "echovault, version test"\n'
        "else\n"
        '  printf "%s\\n" "$*" >> "$MEMORY_CALLS_FILE"\n'
        "fi\n"
    )
    memory.chmod(0o755)

    env = os.environ.copy()
    env.update({
        "HOME": str(home),
        "PATH": f"{fake_bin}:{home / '.local' / 'bin'}:/usr/bin:/bin",
        "MEMORY_CALLS_FILE": str(calls_file),
    })
    result = subprocess.run(
        ["sh", str(INSTALLER), "--agent", "codex", "--project"],
        capture_output=True,
        text=True,
        env=env,
    )

    assert result.returncode == 0, result.stderr
    assert calls_file.read_text().splitlines() == [
        "init",
        "setup codex --project",
    ]
