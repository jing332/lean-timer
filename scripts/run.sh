#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

pick_python() {
  local candidates=()

  if [[ -n "${PYTHON:-}" ]]; then
    candidates+=("${PYTHON}")
  fi

  if [[ -x .venv/bin/python ]]; then
    candidates+=(".venv/bin/python")
  fi

  candidates+=("/usr/bin/python3" "python3")

  local candidate
  for candidate in "${candidates[@]}"; do
    if command -v "$candidate" >/dev/null 2>&1 && "$candidate" -c "import gi" >/dev/null 2>&1; then
      printf '%s\n' "$candidate"
      return 0
    fi
  done

  printf '%s\n' "/usr/bin/python3"
}

PYTHON_BIN="$(pick_python)"

if [[ ! -d .venv ]]; then
  python3 -m venv --system-site-packages .venv
fi

PYTHONPATH=src "$PYTHON_BIN" -m lean_timer --self-check

PYTHONPATH=src "$PYTHON_BIN" -m lean_timer
