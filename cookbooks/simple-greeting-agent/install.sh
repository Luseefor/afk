#!/usr/bin/env bash
set -euo pipefail

# install.sh — install runtime deps and local `afk` package for this cookbook
# Usage:
#   ./install.sh            # create .venv, install deps and editable afk
#   ./install.sh --run      # also run `uv run main.py` after install
#   ./install.sh --python /path/to/python

print_usage() {
  cat <<'USAGE'
Usage: install.sh [--python /path/to/python] [--run] [--help]

Creates a local virtualenv in this cookbook (./.venv), installs the
project (editable) from the repository root and ensures `uv` is
available so you can run `uv run main.py`.
USAGE
}

# --- arg parsing ---
PYTHON=""
DO_RUN=0
while [[ $# -gt 0 ]]; do
  case "$1" in
    --python)
      PYTHON="$2"; shift 2;;
    --run)
      DO_RUN=1; shift ;;
    -h|--help)
      print_usage; exit 0 ;;
    *)
      echo "Unknown arg: $1" >&2; print_usage; exit 2 ;;
  esac
done

# find python executable
if [[ -n "$PYTHON" ]]; then
  PY="$PYTHON"
elif command -v python3.13 >/dev/null 2>&1; then
  PY=python3.13
elif command -v python3 >/dev/null 2>&1; then
  PY=python3
elif command -v python >/dev/null 2>&1; then
  PY=python
else
  echo "No suitable Python interpreter found (need Python >= 3.13)." >&2
  exit 1
fi

# make paths absolute
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
cd "$SCRIPT_DIR"

echo "Using Python: $(command -v $PY || echo $PY)"
echo "Repository root: $REPO_ROOT"

# create venv if missing
if [[ ! -d .venv ]]; then
  echo "Creating virtualenv in ./ .venv ..."
  $PY -m venv .venv
fi

# activate
# shellcheck disable=SC1091
source .venv/bin/activate

# ensure pip tooling is recent
pip install --upgrade pip setuptools wheel

# make sure `uv` CLI is available (used for `uv run`)
if ! command -v uv >/dev/null 2>&1; then
  echo "Installing 'uv' CLI into the virtualenv..."
  pip install --upgrade uv
else
  echo "'uv' CLI already available in virtualenv"
fi

# install the local package (editable) so `import afk` works
echo "Installing local package (editable) from repo root..."
pip install -e "$REPO_ROOT"

echo "\n✅ Installation complete. Activate with: source .venv/bin/activate"
echo "Then run the cookbook: uv run main.py"

if [[ $DO_RUN -eq 1 ]]; then
  echo "\nRunning: uv run main.py"
  uv run main.py
fi
