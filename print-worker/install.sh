#!/usr/bin/env bash
# Install print-worker as a user LaunchAgent.
# Run from the print-worker dir: ./install.sh

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PLIST_NAME="com.dosscodesigns.print-worker.plist"
PLIST_SRC="$SCRIPT_DIR/$PLIST_NAME"
LAUNCHAGENTS="$HOME/Library/LaunchAgents"
PLIST_DST="$LAUNCHAGENTS/$PLIST_NAME"

mkdir -p "$LAUNCHAGENTS"

if [[ -L "$PLIST_DST" || -f "$PLIST_DST" ]]; then
  launchctl bootout "gui/$(id -u)/com.dosscodesigns.print-worker" 2>/dev/null || true
  rm -f "$PLIST_DST"
fi

ln -s "$PLIST_SRC" "$PLIST_DST"
launchctl bootstrap "gui/$(id -u)" "$PLIST_DST"
launchctl enable "gui/$(id -u)/com.dosscodesigns.print-worker"

echo "Installed. Verify:"
echo "  launchctl print gui/$(id -u)/com.dosscodesigns.print-worker | head -20"
echo "  curl -s http://localhost:3001/health"
