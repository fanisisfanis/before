#!/usr/bin/env bash
set -euo pipefail
cd -- "$(dirname -- "${BASH_SOURCE[0]}")"
if ! command -v python3 >/dev/null 2>&1; then
  printf 'BEFORE needs Python 3.10 or later. Install Python and try again.\n' >&2
  exit 1
fi
python3 -c 'import sys; assert (3, 10) <= sys.version_info < (3, 14), "Python 3.10-3.13 required; use the portable build with newer system Python"'
if [[ ! -x .venv/bin/python ]]; then
  python3 -m venv .venv
fi
if ! .venv/bin/python -c 'import PySide6.QtWidgets' >/dev/null 2>&1; then
  .venv/bin/python -m pip install -r requirements.txt
fi
exec .venv/bin/python run.py "$@"
