#!/bin/bash
# Uninstall MIDI Controller daemon (LaunchAgent)

set -e

PLIST_NAME="com.midi-controller.agent"
PLIST_PATH="$HOME/Library/LaunchAgents/${PLIST_NAME}.plist"

if [ ! -f "$PLIST_PATH" ]; then
    echo "LaunchAgent not installed at: $PLIST_PATH"
    exit 0
fi

echo "Stopping and unloading service..."
launchctl unload "$PLIST_PATH" 2>/dev/null || true

echo "Removing plist..."
rm "$PLIST_PATH"

echo "MIDI Controller daemon uninstalled."
