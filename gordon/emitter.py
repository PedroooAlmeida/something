"""Writes roast events as JSON files into roast_events/."""
import datetime
import json
import os
import uuid


class Emitter:
    def __init__(self, events_dir):
        self.events_dir = events_dir
        os.makedirs(events_dir, exist_ok=True)

    def write(self, event: dict) -> str:
        event = dict(event)
        event["event_id"] = str(uuid.uuid4())
        event["iso"] = datetime.datetime.fromtimestamp(
            event["ts"], datetime.timezone.utc).isoformat()
        path = os.path.join(
            self.events_dir, f"{int(event['ts'] * 1000)}_{event['kind']}.json")
        with open(path, "w") as f:
            json.dump(event, f, indent=2)
        blurb = event.get("summary") or event.get("evidence", "")
        print(f"[gordon] 🔥 {event['kind']} — {blurb}  → {path}")
        return path
