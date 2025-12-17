import json
import os
import subprocess
import sys
import requests

from dotenv import load_dotenv
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo

BASE = Path(__file__).resolve().parent
load_dotenv(BASE / "env" / "discord_hook.env", override=True)

NY = ZoneInfo("America/New_York")
UTC = ZoneInfo("UTC")


def parse_iso_dt(s: str) -> datetime | None:
    if not s:
        return None
    # Handle trailing 'Z' (UTC) and fractional seconds
    s = s.strip().replace("Z", "+00:00")
    return datetime.fromisoformat(s)


def ensure_tz(dt: datetime | None) -> datetime | None:
    if dt is None:
        return None
    # If the producer ever returns naive datetimes, assume UTC
    if dt.tzinfo is None:
        return dt.replace(tzinfo=UTC)
    return dt


def fmt_time_local(dt: datetime | None) -> str:
    if dt is None:
        return "?"
    local = dt.astimezone(NY)
    # Cross-platform hour formatting: %I works on Windows; strip leading zero.
    return local.strftime("%I:%M %p").lstrip("0")


def fmt_day_local(dt: datetime | None) -> str:
    if dt is None:
        return "?"
    local = dt.astimezone(NY)
    # Example: "Wed 12/17"
    return local.strftime("%a %m/%d")


def main():
    webhook = (os.environ.get("DISCORD_WEBHOOK_URL") or "").strip()
    print("Using webhook repr:", repr(webhook))

    if not webhook:
        print("Missing DISCORD_WEBHOOK_URL environment variable.", file=sys.stderr)
        sys.exit(2)

    # Run Swift producer
    swift_bin = BASE / "build" / "calendar"
    out = subprocess.check_output([str(swift_bin)], text=True)
    data = json.loads(out)

    events = data.get("events", [])
    if not events:
        content = "No events today."
    else:
        lines = []
        for e in events:
            title = e.get("title", "(No title)")
            loc = e.get("location")
            loc_part = f" @ {loc}" if loc else ""

            if e.get("allDay"):
                # If your Swift producer provides a date field for all-day events,
                # you can include it here similarly. For now, keep it simple.
                when = "All day"
            else:
                start_dt = ensure_tz(parse_iso_dt(e.get("start")))
                end_dt = ensure_tz(parse_iso_dt(e.get("end")))

                day = fmt_day_local(start_dt)
                start = fmt_time_local(start_dt)
                end = fmt_time_local(end_dt)

                when = f"{day} {start}–{end} ET"

            lines.append(f"{when}: {title}{loc_part}")

        content = "\n".join(lines)

    resp = requests.post(webhook, json={"content": content}, timeout=15)

    if resp.status_code not in (200, 204):
        print(f"Webhook failed: HTTP {resp.status_code}\n{resp.text}", file=sys.stderr)
        sys.exit(1)

    print(f"Posted. HTTP {resp.status_code}")

if __name__ == "__main__":
    main()
