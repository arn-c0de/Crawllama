#!/bin/bash
# Shared helper: give uv a usable virtualenv location.
#
# VirtualBox/VMware shared folders (vboxsf / vmhgfs) cannot create symlinks.
# uv's default in-project ".venv" symlinks the Python interpreter, so on such a
# folder `uv sync` / `uv run` fail with:
#   "failed to symlink file ... Operation not permitted"
#   ".venv ... is not a valid Python environment (no Python executable found)"
#
# When the project directory can't hold symlinks, relocate the environment off
# the share (into the user's data dir) and tell uv to copy instead of link.
# Source this file from the run/setup scripts BEFORE any `uv` call:
#   source "<project>/scripts/uv-env.sh"
#   crawllama_setup_uv_env "<project_dir>"

crawllama_setup_uv_env() {
    # Respect an explicit user override — do nothing if already set.
    [ -n "$UV_PROJECT_ENVIRONMENT" ] && return 0

    local project_dir="$1"
    [ -z "$project_dir" ] && project_dir="$PWD"

    # Probe: can we create a symlink in the project dir?
    local probe="$project_dir/.uv-symlink-probe.$$"
    rm -f "$probe" 2>/dev/null
    if ln -s . "$probe" 2>/dev/null; then
        rm -f "$probe" 2>/dev/null
        return 0   # symlinks work → default in-project .venv is fine
    fi
    rm -f "$probe" 2>/dev/null

    # No symlink support. Relocate the venv to a native filesystem. Derive a
    # stable per-checkout name so different project paths don't collide.
    local key
    key="$(printf '%s' "$project_dir" | cksum | awk '{print $1}')"
    export UV_PROJECT_ENVIRONMENT="${XDG_DATA_HOME:-$HOME/.local/share}/crawllama/venv-$key"
    export UV_LINK_MODE=copy

    # Remove a broken in-project .venv left by an earlier failed `uv sync`, so a
    # stale directory can't shadow the relocated environment.
    if [ -d "$project_dir/.venv" ] && [ ! -x "$project_dir/.venv/bin/python" ]; then
        rm -rf "$project_dir/.venv" 2>/dev/null
    fi

    echo "[INFO] Shared folder without symlink support detected (e.g. VirtualBox vboxsf)."
    echo "       Relocating the virtualenv off the share to:"
    echo "         $UV_PROJECT_ENVIRONMENT"
}
