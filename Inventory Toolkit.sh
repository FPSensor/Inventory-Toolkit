#!/usr/bin/env bash
# Inventory Toolkit — Linux/macOS launcher
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"
exec python3 cli.py "$@"
