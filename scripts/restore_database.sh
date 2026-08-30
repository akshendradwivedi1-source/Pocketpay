#!/usr/bin/env bash
# PocketPay Linux/macOS Database Restore Runner
set -e
DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )/.." >/dev/null 2>&1 && pwd )"
cd "$DIR"

if [ -f ".venv/bin/python" ]; then
    .venv/bin/python scripts/restore_database.py "$@"
else
    python3 scripts/restore_database.py "$@"
fi
