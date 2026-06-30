#!/usr/bin/env bash
# Install + (re)load the launchd agent that refreshes calendar.ics on a timer.
# Usage: ./setup-launchd.sh [interval_seconds]   (default 900 = 15 min)
set -euo pipefail

REPO="$(cd "$(dirname "$0")" && pwd)"
LABEL="com.mike.dclt-badminton-ics"
PLIST="$HOME/Library/LaunchAgents/$LABEL.plist"
INTERVAL="${1:-900}"

mkdir -p "$HOME/Library/LaunchAgents"
cat > "$PLIST" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
  <key>Label</key><string>$LABEL</string>
  <key>ProgramArguments</key><array>
    <string>/bin/zsh</string><string>-lc</string>
    <string>$REPO/publish-local.sh</string>
  </array>
  <key>StartInterval</key><integer>$INTERVAL</integer>
  <key>RunAtLoad</key><true/>
  <key>StandardOutPath</key><string>/tmp/dclt-badminton-ics.log</string>
  <key>StandardErrorPath</key><string>/tmp/dclt-badminton-ics.err</string>
</dict></plist>
EOF

launchctl unload "$PLIST" 2>/dev/null || true
launchctl load "$PLIST"

echo "Installed + loaded $LABEL (every ${INTERVAL}s) -> $REPO/publish-local.sh"
launchctl list | grep dclt-badminton || { echo "WARN: agent not listed"; exit 1; }
