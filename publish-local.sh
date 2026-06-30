#!/usr/bin/env bash
# Generate the ICS locally (DCLT API only answers UK-residential IPs) and push to GitHub.
# Run on a schedule via launchd (com.mike.dclt-badminton-ics.plist). Commits only on real change.
set -euo pipefail
cd "$(dirname "$0")"

python3 gen_ics.py 2

# Strip volatile lines so timestamp churn alone never commits.
norm() { grep -vE '^DTSTAMP' "$1" | sed 's/Checked:[^\\]*/Checked:/'; }
if git show HEAD:calendar.ics > /tmp/dclt-old.ics 2>/dev/null \
   && diff -q <(norm /tmp/dclt-old.ics) <(norm calendar.ics) >/dev/null; then
  echo "$(date '+%F %T') no meaningful change"
  exit 0
fi

git add calendar.ics
git commit -m "chore: refresh badminton ICS [skip ci]"
git push origin main
echo "$(date '+%F %T') pushed refreshed ICS"
