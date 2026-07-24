#!/bin/sh

set -eu

ECHOVAULT_RELEASE="${ECHOVAULT_VERSION:-main}"
AGENT=""
PROJECT=false
RUN_SETUP=true
INSTALLER=""

usage() {
    cat <<'EOF'
Install EchoVault in an isolated environment and configure a coding agent.

Usage:
  install.sh [--agent AGENT] [--project] [--no-setup] [--version VERSION]

Options:
  --agent AGENT       Configure claude-code, cursor, codex, or opencode
  --project           Write agent configuration in the current project
  --no-setup          Install only; do not launch `memory setup`
  --version VERSION   Install a release tag or branch (default: main)
  -h, --help          Show this help

Environment:
  ECHOVAULT_VERSION       Release tag or branch to install
  ECHOVAULT_INSTALL_DIR   Fallback venv location
  ECHOVAULT_BIN_DIR       Fallback command location
EOF
}

die() {
    printf 'Error: %s\n' "$*" >&2
    exit 1
}

while [ "$#" -gt 0 ]; do
    case "$1" in
        --agent)
            [ "$#" -ge 2 ] || die "--agent requires a value"
            AGENT="$2"
            shift 2
            ;;
        --project)
            PROJECT=true
            shift
            ;;
        --no-setup)
            RUN_SETUP=false
            shift
            ;;
        --version)
            [ "$#" -ge 2 ] || die "--version requires a value"
            ECHOVAULT_RELEASE="$2"
            shift 2
            ;;
        -h|--help)
            usage
            exit 0
            ;;
        *)
            die "unknown option: $1 (use --help for usage)"
            ;;
    esac
done

case "$AGENT" in
    ""|claude-code|cursor|codex|opencode) ;;
    *) die "unsupported agent '$AGENT' (choose claude-code, cursor, codex, or opencode)" ;;
esac

case "$ECHOVAULT_RELEASE" in
    *[!A-Za-z0-9._/-]*|"") die "invalid version or branch: $ECHOVAULT_RELEASE" ;;
esac

command -v git >/dev/null 2>&1 || die "git is required but was not found on PATH"

PACKAGE_SPEC="git+https://github.com/mraza007/echovault.git@${ECHOVAULT_RELEASE}"

printf 'Installing EchoVault %s...\n' "$ECHOVAULT_RELEASE"

if command -v uv >/dev/null 2>&1; then
    uv tool install --force "$PACKAGE_SPEC"
    INSTALLER="uv"
elif command -v pipx >/dev/null 2>&1; then
    pipx install --force "$PACKAGE_SPEC"
    INSTALLER="pipx"
else
    PYTHON=""
    if command -v python3 >/dev/null 2>&1; then
        PYTHON="$(command -v python3)"
    elif command -v python >/dev/null 2>&1; then
        PYTHON="$(command -v python)"
    fi
    [ -n "$PYTHON" ] || die "Python 3.10 or newer is required"
    "$PYTHON" -c 'import sys; raise SystemExit(0 if sys.version_info >= (3, 10) else 1)' ||
        die "Python 3.10 or newer is required"

    INSTALL_DIR="${ECHOVAULT_INSTALL_DIR:-$HOME/.local/share/echovault}"
    BIN_DIR="${ECHOVAULT_BIN_DIR:-$HOME/.local/bin}"
    MEMORY_TARGET="$INSTALL_DIR/venv/bin/memory"
    MEMORY_LINK="$BIN_DIR/memory"

    "$PYTHON" -m venv "$INSTALL_DIR/venv"
    "$INSTALL_DIR/venv/bin/python" -m pip install --upgrade "$PACKAGE_SPEC"
    mkdir -p "$BIN_DIR"

    if [ -e "$MEMORY_LINK" ] || [ -L "$MEMORY_LINK" ]; then
        CURRENT_TARGET="$(readlink "$MEMORY_LINK" 2>/dev/null || true)"
        [ "$CURRENT_TARGET" = "$MEMORY_TARGET" ] ||
            die "$MEMORY_LINK already exists and is not managed by this installer"
    else
        ln -s "$MEMORY_TARGET" "$MEMORY_LINK"
    fi
    INSTALLER="venv"
fi

MEMORY_CMD=""
if command -v memory >/dev/null 2>&1; then
    CANDIDATE="$(command -v memory)"
    if "$CANDIDATE" --version 2>/dev/null | grep -qi echovault; then
        MEMORY_CMD="$CANDIDATE"
    fi
fi

if [ -z "$MEMORY_CMD" ] && [ -x "$HOME/.local/bin/memory" ]; then
    if "$HOME/.local/bin/memory" --version 2>/dev/null | grep -qi echovault; then
        MEMORY_CMD="$HOME/.local/bin/memory"
    fi
fi

printf 'Installed with %s.\n' "$INSTALLER"

if [ -z "$MEMORY_CMD" ]; then
    printf '\nEchoVault was installed, but memory is not on PATH yet.\n'
    case "$INSTALLER" in
        uv) printf 'Run "uv tool update-shell", open a new terminal, then run "memory setup".\n' ;;
        pipx) printf 'Run "pipx ensurepath", open a new terminal, then run "memory setup".\n' ;;
        venv) printf 'Add %s to PATH, open a new terminal, then run "memory setup".\n' "${ECHOVAULT_BIN_DIR:-$HOME/.local/bin}" ;;
    esac
    exit 0
fi

if [ "$RUN_SETUP" = true ]; then
    "$MEMORY_CMD" init
    if [ -n "$AGENT" ]; then
        if [ "$PROJECT" = true ]; then
            "$MEMORY_CMD" setup "$AGENT" --project
        else
            "$MEMORY_CMD" setup "$AGENT"
        fi
    elif ( : </dev/tty ) 2>/dev/null; then
        if [ "$PROJECT" = true ]; then
            "$MEMORY_CMD" setup --project </dev/tty
        else
            "$MEMORY_CMD" setup </dev/tty
        fi
    else
        printf '\nRun "memory setup" to configure your coding agent.\n'
    fi
fi

printf '\nEchoVault is ready.\n'
