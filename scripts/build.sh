#!/usr/bin/env bash
# Optional PyInstaller template for 桌宠grok. Safe to run from repo root.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

if ! command -v pyinstaller >/dev/null 2>&1; then
  echo "pyinstaller not found. Install with: pip install 'pyinstaller>=6.0'" >&2
  exit 1
fi

# macOS/Linux data separator is ':'; Windows users should use ';' instead.
pyinstaller \
  --noconfirm \
  --windowed \
  --name "桌宠grok" \
  --add-data "assets:assets" \
  run.py

echo "Done. See dist/ for 桌宠grok.app (or binary)."
