#!/usr/bin/env python3
"""Self-check for the sport-aware slot key. Run: python3 test_slot_key.py"""
import datetime as dt
import hashlib
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent / "checker"))

from dclt_checker_service import TZ, slot_key  # noqa: E402

start = dt.datetime(2026, 8, 13, 13, 0, tzinfo=TZ)
end = dt.datetime(2026, 8, 13, 14, 0, tzinfo=TZ)

bad = slot_key("DOME", "The Dome", start, end, "Badminton")
squ = slot_key("DOME", "The Dome", start, end, "Squash")

# Same venue + same start/end, different sport -> distinct events, no silent merge.
assert bad != squ, "sport must be part of the slot key"

# Badminton keys must not churn: unchanged from the pre-squash format, and the
# default arg still reproduces them for any caller that omits the sport.
assert bad == slot_key("DOME", "The Dome", start, end), "badminton key must be stable"
legacy_raw = f"DOME|The Dome|{start.isoformat()}|{end.isoformat()}"  # pre-squash format
assert bad == hashlib.sha1(legacy_raw.encode()).hexdigest()[:16], "badminton UIDs would churn"

print("ok")
