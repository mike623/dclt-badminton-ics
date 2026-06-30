# Handover: DCLT Badminton → n8n / Calendar POC

_Last updated: 2026-06-30 16:10 Europe/London_

## Goal

Build a proof-of-concept that takes DCLT GladstoneGo badminton availability and makes it usable by n8n / Google Calendar sharing.

Target flow:

```text
DCLT GladstoneGo API
  → local checker service
  → structured JSON + ICS feed
  → n8n workflow
  → Google Calendar events / shared calendar
```

## Project location

```text
/Users/mikewong/workspace/n8n-badminton-poc
```

Important files:

```text
checker/dclt_checker_service.py       # Python stdlib HTTP service for DCLT availability
checker/Containerfile                 # Podman image for checker service
run-poc.sh                            # Starts checker + n8n containers
stop-poc.sh                           # Stops checker + n8n containers
workflows/dclt-badminton-poc.json     # Importable n8n workflow draft
output/                               # Optional generated files, e.g. ICS exports
n8n/                                  # n8n Podman volume/data dir
n8n-host/                             # Host-run n8n experiment dir from earlier workaround
```

## Current live state at handover

Verified just before writing this handover:

```text
http://localhost:8787/healthz          → {"ok": true, "service": "dclt-badminton-n8n-poc"}
http://localhost:5678/healthz          → {"status":"ok"}
http://localhost:8787/availability?days=2
  checked_at: 2026-06-30T16:06:47.722559+01:00
  slot_count: 31
  errors: []
http://localhost:8787/calendar.ics?days=2
  ICS events: 31
  ICS bytes: 20127
```

Podman also showed:

```text
dclt-badminton-checker  Up  ...  0.0.0.0:8787->8787/tcp
n8n-badminton-poc       Up  ...  0.0.0.0:5678->5678/tcp
```

If state has changed, re-check with:

```bash
podman ps --format '{{.Names}}\t{{.Status}}\t{{.Ports}}' | grep -E 'dclt|n8n' || true
curl -fsS http://localhost:8787/healthz
curl -fsS http://localhost:5678/healthz
```

## Run / stop commands

Start both services:

```bash
cd /Users/mikewong/workspace/n8n-badminton-poc
./run-poc.sh
```

Stop both services:

```bash
cd /Users/mikewong/workspace/n8n-badminton-poc
./stop-poc.sh
```

Manual stop if needed:

```bash
podman rm -f n8n-badminton-poc dclt-badminton-checker
pkill -f 'node.*n8n.*start' 2>/dev/null || true
```

## Checker service

The checker is intentionally simple and uses only Python stdlib:

```text
checker/dclt_checker_service.py
```

Endpoints:

```text
GET /healthz
GET /availability?days=2
GET /calendar.ics?days=2
```

Example checks:

```bash
curl -fsS http://localhost:8787/healthz
curl -fsS 'http://localhost:8787/availability?days=2' | python3 -m json.tool | less
curl -fsS 'http://localhost:8787/calendar.ics?days=2' -o output/badminton.ics
```

The JSON output shape is roughly:

```json
{
  "checked_at": "2026-06-30T16:06:47.722559+01:00",
  "timezone": "Europe/London",
  "manager": "dclt-badminton-n8n-poc",
  "excluded_sites": ["ADW"],
  "slot_count": 31,
  "slots": [
    {
      "id": "stable-slot-key",
      "venue": "Dearne Valley Leisure",
      "title": "Dearne Valley Leisure Badminton",
      "start": "2026-06-30T17:00:00+01:00",
      "end": "2026-06-30T17:59:59+01:00",
      "courts": ["Court 1", "Court 2"],
      "booking_url": "https://dclt.gladstonego.cloud/book/calendar/...",
      "source": "dclt_api_availability_not_pricing_verified"
    }
  ],
  "errors": []
}
```

### DCLT API facts

The checker reproduces the GladstoneGo anonymous SSO flow:

```text
GET /api/samlauthentication/anonymous
GET /api/samlauthentication/authentication-status
GET /api/search/activities/?siteIds=<SITE>&webBookableOnly=true
GET /api/availability/V2/sessions?webBookableOnly=true&siteIds=<SITE>&activityIds=<ACTIVITY>&dateFrom=<ISO>
```

Required header:

```text
X-Use-Sso: 1
```

User preference baked in:

```text
Exclude Adwick / ADW
```

Important limitation:

```text
The checker verifies API availability only. It does NOT verify final pricing/purchase availability.
Past live UI checks showed some API-available slots can fail later at /api/pricing/session.
Do not claim final bookability unless pricing/live booking flow is added.
```

## n8n workflow

Workflow file:

```text
workflows/dclt-badminton-poc.json
```

Draft workflow structure:

```text
Manual Trigger
  → Fetch DCLT availability
  → Build calendar event payloads
  → Build Telegram summary / event batch
  → Sticky note describing Google Calendar next step
```

The workflow is intentionally safe: it does not mutate Google Calendar yet.

The HTTP Request node should call one of:

```text
Inside Podman network:
http://dclt-badminton-checker:8787/availability?days=2

From host/local n8n:
http://localhost:8787/availability?days=2
```

If importing manually, open:

```text
http://localhost:5678
```

Then import:

```text
/Users/mikewong/workspace/n8n-badminton-poc/workflows/dclt-badminton-poc.json
```

## Google Calendar implementation plan

Recommended calendar model:

```text
Dedicated calendar: DCLT Badminton Availability
Share that calendar with the other person.
```

Event strategy:

- One event per venue/time slot, not one event per court.
- Group courts into the description.
- Use `slot.id` as the stable key.
- Include a managed marker in description:

```text
Managed by: dclt-badminton-n8n-poc
Slot key: <slot.id>
```

Event fields from checker JSON:

```text
summary     = slot.title
start       = slot.start
end         = slot.end
location    = slot.venue
description = Courts + Booking URL + Checked timestamp + Managed marker + Slot key
```

For proper upsert/delete in n8n:

1. Fetch availability JSON.
2. Search calendar events in the next N days where description contains `Managed by: dclt-badminton-n8n-poc`.
3. Build desired event set keyed by `Slot key`.
4. Create missing events.
5. Update changed events.
6. Delete stale managed events not present in current desired set.

Avoid duplicate spam by never blindly creating events without searching existing managed events first.

## ICS alternative

The checker already exposes an ICS feed:

```text
http://localhost:8787/calendar.ics?days=2
```

This can be hosted publicly and subscribed to in Google Calendar. This avoids Google OAuth but has one major downside: Google Calendar can refresh subscribed ICS feeds slowly.

Potential simple path:

```bash
curl -fsS 'http://localhost:8787/calendar.ics?days=2' \
  -o /some/static-host/badminton.ics
```

Then share the hosted ICS URL.

## Problems hit during this session

### 1. Podman VM disk too small initially

Initial n8n image pull failed with `no space left on device` because Podman machine disk was 13GB and full.

Useful diagnostics:

```bash
podman machine list
podman machine ssh df -h /
podman system df
```

Cleanup performed:

```bash
echo 'y' | podman system prune -a --volumes
```

At handover, Podman VM had roughly:

```text
/dev/vda4  13G  11G  2.2G  84% /
```

If n8n image pulls fail again, increase Podman machine disk or prune more.

### 2. Host-run n8n experiment created extra state

A temporary host-run n8n experiment was attempted under:

```text
n8n-host/
```

It produced API key experiments and sqlite state. It is not required for the Podman POC. Prefer using the Podman `n8n/` volume going forward.

### 3. n8n API auth / import experiments were messy

The `/api/v1/workflows` API had 401/500 issues while using manually inserted API keys. Do not continue that path unless necessary.

Prefer manual UI import or official n8n CLI/import inside the container.

If using CLI import inside the n8n container, try:

```bash
podman exec -it n8n-badminton-poc n8n import:workflow --input=/files/dclt-badminton-poc.json
```

But currently `workflows/` is not mounted into the n8n container; only `output/` is mounted to `/files`. Either:

- temporarily copy the workflow JSON into `output/`, or
- add another volume mount in `run-poc.sh`:

```bash
-v "$PWD/workflows:/workflows:U,Z"
```

Then import:

```bash
podman exec -it n8n-badminton-poc n8n import:workflow --input=/workflows/dclt-badminton-poc.json
```

## Security / cleanup notes

There is/was a local file:

```text
.n8n-api-key
```

It was created during failed API auth experiments. Treat it as throwaway. Do not commit or share it. Prefer deleting it and creating API keys through the n8n UI if needed.

Suggested cleanup before committing/sharing this POC:

```bash
cd /Users/mikewong/workspace/n8n-badminton-poc
rm -f .n8n-api-key fetch-workflows.sh fetch_workflows.py test_api.py test_api2.py
```

Also avoid committing local n8n data dirs:

```text
n8n/
n8n-host/
.omc/
output/
```

Recommended `.gitignore` if this becomes a repo:

```gitignore
n8n/
n8n-host/
.omc/
output/
.n8n-api-key
fetch-workflows.sh
fetch_workflows.py
test_api.py
test_api2.py
```

## Recommended next action for the next agent

Best next path:

1. Keep checker service as-is.
2. Clean up host-run n8n artifacts if desired.
3. Add workflow volume mount to `run-poc.sh`.
4. Import workflow inside the Podman n8n container or through UI.
5. Manually verify workflow can fetch `http://dclt-badminton-checker:8787/availability?days=2`.
6. Add Google Calendar credentials in n8n UI.
7. Implement managed-event upsert/delete using `slot.id`.
8. Only after Google Calendar works, decide whether to replace Hermes cron or keep Hermes cron as a separate personal Telegram alert.

## Quick verification checklist

```bash
cd /Users/mikewong/workspace/n8n-badminton-poc

# Services
podman ps --format '{{.Names}}\t{{.Status}}\t{{.Ports}}' | grep -E 'dclt|n8n'

# Checker health
curl -fsS http://localhost:8787/healthz

# Availability JSON
curl -fsS 'http://localhost:8787/availability?days=2' -o /tmp/dclt-avail.json
python3 - <<'PY'
import json
p=json.load(open('/tmp/dclt-avail.json'))
print('slot_count', p['slot_count'])
print('errors', p['errors'])
print('first_slot', p['slots'][0] if p['slots'] else None)
PY

# ICS
curl -fsS 'http://localhost:8787/calendar.ics?days=2' -o /tmp/dclt.ics
python3 - <<'PY'
s=open('/tmp/dclt.ics').read()
print('events', s.count('BEGIN:VEVENT'))
print(s.splitlines()[:10])
PY

# n8n health
curl -fsS http://localhost:5678/healthz
```

## Related Hermes skill/reference

Loaded skill:

```text
booking-availability-automation
```

Relevant installed reference:

```text
/Users/mikewong/.hermes/skills/web-automation/booking-availability-automation/references/dclt-gladstonego-badminton.md
```

Original daily Hermes cron script still exists separately:

```text
/Users/mikewong/.hermes/scripts/dclt_badminton.py
```

That script is the production-ish personal Telegram alert path. This POC is separate and should not break it.
