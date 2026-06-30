#!/usr/bin/env python3
"""DCLT badminton availability service for n8n POC.

Endpoints:
  GET /healthz
  GET /availability?days=2
  GET /calendar.ics?days=2

Uses only Python stdlib and the DCLT GladstoneGo anonymous SSO/API flow.
"""
from __future__ import annotations

import datetime as dt
import hashlib
import http.cookiejar
import json
import os
import sys
import urllib.parse
import urllib.request
from collections import defaultdict
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from zoneinfo import ZoneInfo

BASE = "https://dclt.gladstonego.cloud"
TZ = ZoneInfo("Europe/London")
MANAGER = "dclt-badminton-n8n-poc"

SITES = {
    # Excluded by user preference.
    # "ADW": "Adwick Leisure Complex",
    "ARM": "Armthorpe Leisure Centre",
    "ASK": "Askern Leisure Centre",
    "FV8": "Choose Fitness Balby",
    "CROOK": "Crookhill Park Golf Course",
    "DVLC": "Dearne Valley Leisure",
    "ROSS": "Rossington Leisure Centre",
    "DOME": "The Dome",
    "THORN": "Thorne Leisure Centre",
}

HEADERS = {
    "Accept": "application/json, text/plain, */*",
    "X-Use-Sso": "1",
    "User-Agent": "Mozilla/5.0 (Hermes DCLT badminton n8n POC)",
    "Referer": BASE + "/book",
}


def api_get(opener, path, *, expect_json=True):
    url = path if path.startswith("http") else BASE + path
    req = urllib.request.Request(url, headers=HEADERS)
    with opener.open(req, timeout=30) as resp:
        body = resp.read().decode("utf-8", "replace")
        if expect_json:
            return json.loads(body) if body else None
        return body


def bootstrap_session():
    jar = http.cookiejar.CookieJar()
    opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))
    api_get(opener, "/api/samlauthentication/anonymous", expect_json=False)
    api_get(opener, "/api/samlauthentication/authentication-status")
    return opener


def iso_z(d: dt.datetime) -> str:
    return d.astimezone(dt.timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def get_badminton_activities(opener, site_id: str):
    path = f"/api/search/activities/?siteIds={urllib.parse.quote(site_id)}&webBookableOnly=true"
    activities = api_get(opener, path) or []
    return [a for a in activities if "badminton" in (a.get("name") or a.get("description") or "").lower()]


def get_availability(opener, site_id: str, activity_id: str, date_from: dt.datetime):
    params = urllib.parse.urlencode({
        "webBookableOnly": "true",
        "siteIds": site_id,
        "activityIds": activity_id,
        "dateFrom": iso_z(date_from),
    })
    return api_get(opener, f"/api/availability/V2/sessions?{params}") or []


def slot_to_local(slot):
    start = dt.datetime.fromisoformat(slot["startTime"].replace("Z", "+00:00")).astimezone(TZ)
    end = dt.datetime.fromisoformat(slot["endTime"].replace("Z", "+00:00")).astimezone(TZ)
    return start, end


def slot_key(site_id: str, venue: str, start: dt.datetime, end: dt.datetime) -> str:
    raw = f"{site_id}|{venue}|{start.isoformat()}|{end.isoformat()}"
    return hashlib.sha1(raw.encode()).hexdigest()[:16]


def calendar_url(activity_id: str, start: dt.datetime) -> str:
    return f"{BASE}/book/calendar/{urllib.parse.quote(activity_id)}?activityDate={urllib.parse.quote(iso_z(start))}"


def collect(days: int = 2) -> dict:
    days = max(1, min(days, 7))
    now = dt.datetime.now(TZ)
    today = now.date()
    target_dates = {today + dt.timedelta(days=i) for i in range(days)}

    opener = bootstrap_session()
    by_key: dict[str, dict] = {}
    errors: list[str] = []

    for site_id, site_name in SITES.items():
        try:
            activities = get_badminton_activities(opener, site_id)
        except Exception as e:
            errors.append(f"{site_name}: activity search failed ({type(e).__name__})")
            continue

        for activity in activities:
            aid = activity.get("id")
            aname = activity.get("name") or activity.get("description") or aid
            if not aid:
                continue
            try:
                sessions = get_availability(opener, site_id, aid, now)
            except Exception as e:
                errors.append(f"{site_name} / {aname}: availability failed ({type(e).__name__})")
                continue

            for session in sessions:
                for loc in session.get("locations") or []:
                    court = loc.get("locationNameToDisplay") or "Court"
                    for slot in loc.get("slots") or []:
                        try:
                            start, end = slot_to_local(slot)
                        except Exception:
                            continue
                        if start.date() not in target_dates:
                            continue
                        status = slot.get("status")
                        avail = ((slot.get("availability") or {}).get("inCentre") or 0) > 0
                        if status != "Available" or not avail:
                            continue
                        key = slot_key(site_id, site_name, start, end)
                        event = by_key.setdefault(key, {
                            "id": key,
                            "manager": MANAGER,
                            "source": "dclt_api_availability_not_pricing_verified",
                            "site_id": site_id,
                            "venue": site_name,
                            "title": f"{site_name} Badminton",
                            "date": start.date().isoformat(),
                            "start": start.isoformat(),
                            "end": end.isoformat(),
                            "booking_url": calendar_url(aid, start),
                            "activity_ids": [],
                            "activity_names": [],
                            "courts": [],
                        })
                        if aid not in event["activity_ids"]:
                            event["activity_ids"].append(aid)
                        if aname and aname not in event["activity_names"]:
                            event["activity_names"].append(aname)
                        if court not in event["courts"]:
                            event["courts"].append(court)

    slots = sorted(by_key.values(), key=lambda s: (s["start"], s["venue"]))
    return {
        "checked_at": now.isoformat(),
        "timezone": "Europe/London",
        "days": days,
        "manager": MANAGER,
        "excluded_sites": ["ADW"],
        "slot_count": len(slots),
        "slots": slots,
        "errors": errors,
    }


def ics_escape(text: str) -> str:
    return text.replace("\\", "\\\\").replace(";", "\\;").replace(",", "\\,").replace("\n", "\\n")


def to_ics(payload: dict) -> str:
    stamp = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//Hermes//DCLT Badminton n8n POC//EN",
        "CALSCALE:GREGORIAN",
        "METHOD:PUBLISH",
        "X-WR-CALNAME:DCLT Badminton Availability",
        "X-WR-TIMEZONE:Europe/London",
    ]
    for slot in payload["slots"]:
        start = dt.datetime.fromisoformat(slot["start"]).astimezone(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        end = dt.datetime.fromisoformat(slot["end"]).astimezone(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        desc = "\n".join([
            f"Courts: {', '.join(slot['courts'])}",
            f"Booking: {slot['booking_url']}",
            f"Checked: {payload['checked_at']}",
            f"Managed by: {payload['manager']}",
            f"Slot key: {slot['id']}",
            "Note: API availability only; final booking/pricing not verified.",
        ])
        lines.extend([
            "BEGIN:VEVENT",
            f"UID:{slot['id']}@dclt-badminton-n8n-poc.local",
            f"DTSTAMP:{stamp}",
            f"DTSTART:{start}",
            f"DTEND:{end}",
            f"SUMMARY:{ics_escape(slot['title'])}",
            f"LOCATION:{ics_escape(slot['venue'])}",
            f"DESCRIPTION:{ics_escape(desc)}",
            f"URL:{slot['booking_url']}",
            "END:VEVENT",
        ])
    lines.append("END:VCALENDAR")
    return "\r\n".join(lines) + "\r\n"


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        qs = urllib.parse.parse_qs(parsed.query)
        days = int(qs.get("days", ["2"])[0])
        if parsed.path == "/healthz":
            self.send(200, "application/json", json.dumps({"ok": True, "service": MANAGER}).encode())
            return
        if parsed.path == "/availability":
            self.send(200, "application/json", json.dumps(collect(days), indent=2).encode())
            return
        if parsed.path == "/calendar.ics":
            self.send(200, "text/calendar; charset=utf-8", to_ics(collect(days)).encode())
            return
        self.send(404, "application/json", json.dumps({"error": "not found"}).encode())

    def log_message(self, fmt, *args):
        print(f"{self.address_string()} - {fmt % args}", file=sys.stderr)

    def send(self, status: int, content_type: str, body: bytes):
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


if __name__ == "__main__":
    port = int(os.getenv("PORT", "8787"))
    server = ThreadingHTTPServer(("0.0.0.0", port), Handler)
    print(f"Serving {MANAGER} on :{port}")
    server.serve_forever()
