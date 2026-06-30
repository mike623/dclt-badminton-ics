# n8n Badminton POC

Local proof-of-concept for projecting DCLT badminton availability into an n8n workflow.

## Components

- `checker/` — tiny Python HTTP service using the existing DCLT GladstoneGo anonymous API flow.
- `n8n/` — n8n data volume.
- `output/` — generated files / optional exported ICS.
- `workflows/dclt-badminton-poc.json` — importable n8n workflow.

## Run

```bash
cd /Users/mikewong/workspace/n8n-badminton-poc
./run-poc.sh
```

Then open:

```text
http://localhost:5678
```

Checker endpoints:

```text
http://localhost:8787/healthz
http://localhost:8787/availability?days=2
http://localhost:8787/calendar.ics?days=2
```

## Google Calendar direction

This POC stops at calendar-ready data / ICS. For real Google Calendar sharing, wire the n8n Google Calendar node to a dedicated calendar and upsert events using `slot.id` as the stable key / marker.
