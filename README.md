# DCLT Badminton ICS

Public iCalendar feed of DCLT (GladstoneGo) badminton court availability. Subscribe in Apple Calendar, Google Calendar, Outlook — no auth.

## Feed

```
https://raw.githubusercontent.com/mike623/dclt-badminton-ics/main/calendar.ics
```

Apple Calendar: **File → New Calendar Subscription** → paste URL → set **Location: On My Mac** (localhost not involved; "On My Mac" just means your Mac polls GitHub) → pick auto-refresh.

## How it works

The DCLT API only answers UK-residential IPs — datacenter IPs (incl. GitHub-hosted runners) get `403`. So generation runs **locally**; GitHub only hosts the file:

```
DCLT GladstoneGo API
  → gen_ics.py  (reuses checker/dclt_checker_service.py: collect() + to_ics())
  → calendar.ics
  → git push
  → GitHub serves the public feed
  → Apple / Google / Outlook subscribe
```

- `publish-local.sh` runs on a macOS **launchd** timer every 30 min; commits only when availability actually changes (timestamp churn ignored).
- GitHub Actions (`.github/workflows/publish-ics.yml`) **validates** the committed feed — it cannot generate (API blocks runner IPs).
- Stable per-slot `UID` → calendar clients dedup / update / remove events automatically (no server-side diff).

## Files

| File | Purpose |
|------|---------|
| `gen_ics.py` | Headless ICS generator (stdlib only) |
| `checker/dclt_checker_service.py` | DCLT availability fetch + ICS builder |
| `publish-local.sh` | Generate + push; run by launchd |
| `.github/workflows/publish-ics.yml` | Validates the committed ICS |
| `calendar.ics` | The published feed |

## Manual refresh

```bash
./publish-local.sh
```

## Scheduler (macOS launchd)

Install + load the timer (writes the plist with correct paths, default every 15 min):

```bash
./setup-launchd.sh            # 15 min
./setup-launchd.sh 600        # custom: every 10 min
```

Manage it:

```bash
launchctl unload ~/Library/LaunchAgents/com.mike.dclt-badminton-ics.plist   # stop
launchctl load   ~/Library/LaunchAgents/com.mike.dclt-badminton-ics.plist   # start
launchctl list | grep dclt-badminton                                        # status (2nd col = last exit; 0=ok)
launchctl start  com.mike.dclt-badminton-ics                                # run now
tail -f /tmp/dclt-badminton-ics.log                                         # stdout log
tail -f /tmp/dclt-badminton-ics.err                                         # error log
```

Uninstall: `launchctl unload` then `rm ~/Library/LaunchAgents/com.mike.dclt-badminton-ics.plist`.

Notes: Mac must be awake at fire time; `git push` uses your ssh key (keychain) — push failures show in the `.err` log.

## Notes

- Availability only — final booking/pricing not verified.
- Adwick (ADW) excluded.
- Internal marker string `dclt-badminton-n8n-poc` is kept in UIDs/descriptions for subscriber continuity — changing it would re-create every event for existing subscribers.
