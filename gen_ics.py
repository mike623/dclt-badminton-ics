#!/usr/bin/env python3
"""Headless ICS generator. Reuses the checker's collect()/to_ics() — no HTTP server, stdlib only.

Usage: python3 gen_ics.py [days]   # default days=2, writes ./calendar.ics
"""
import pathlib
import sys

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE / "checker"))

from dclt_checker_service import collect, to_ics  # noqa: E402

days = int(sys.argv[1]) if len(sys.argv) > 1 else 2
out = HERE / "calendar.ics"
# newline="" so the CRLF line endings to_ics() emits are written verbatim (ICS requires CRLF).
out.write_text(to_ics(collect(days)), encoding="utf-8", newline="")
print(f"wrote {out} ({out.stat().st_size} bytes, days={days})")
