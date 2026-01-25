#!/bin/bash
# Install MIDI Controller as a macOS daemon (LaunchAgent)
# This runs the menubar app at login without requiring a terminal

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PLIST_NAME="com.midi-controller.agent"
PLIST_PATH="$HOME/Library/LaunchAgents/${PLIST_NAME}.plist"

# Check for virtual environment
if [ -f "$SCRIPT_DIR/venv/bin/python3" ]; then
    PYTHON_PATH="$SCRIPT_DIR/venv/bin/python3"
elif command -v python3 &> /dev/null; then
    PYTHON_PATH="$(which python3)"
else
    echo "Error: Python 3 not found"
    exit 1
fi

# Check for config file
if [ ! -f "$SCRIPT_DIR/config.yaml" ]; then
    echo "Error: config.yaml not found in $SCRIPT_DIR"
    echo "Run 'python -m midi_controller setup' first to create a configuration."
    exit 1
fi

# Stop existing service if running
if launchctl list | grep -q "$PLIST_NAME"; then
    echo "Stopping existing service..."
    launchctl unload "$PLIST_PATH" 2>/dev/null || true
fi

# Create the plist file
cat > "$PLIST_PATH" << EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>${PLIST_NAME}</string>
    <key>ProgramArguments</key>
    <array>
        <string>${PYTHON_PATH}</string>
        <string>-m</string>
        <string>midi_controller</string>
        <string>menubar</string>
        <string>-c</string>
        <string>${SCRIPT_DIR}/config.yaml</string>
    </array>
    <key>WorkingDirectory</key>
    <string>${SCRIPT_DIR}</string>
    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <false/>
    <key>StandardOutPath</key>
    <string>${HOME}/Library/Logs/midi-controller.log</string>
    <key>StandardErrorPath</key>
    <string>${HOME}/Library/Logs/midi-controller.log</string>
    <key>EnvironmentVariables</key>
    <dict>
        <key>PATH</key>
        <string>/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin</string>
    </dict>
</dict>
</plist>
EOF

echo "Created LaunchAgent at: $PLIST_PATH"

# Load the service
launchctl load "$PLIST_PATH"
echo "Service loaded. MIDI Controller will start at login."
echo ""
echo "To start now:     launchctl start $PLIST_NAME"
echo "To stop:          launchctl stop $PLIST_NAME"
echo "To uninstall:     launchctl unload $PLIST_PATH && rm $PLIST_PATH"
echo "Logs at:          ~/Library/Logs/midi-controller.log"
