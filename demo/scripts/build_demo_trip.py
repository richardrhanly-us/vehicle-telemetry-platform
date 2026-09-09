"""
Build-time utility (not part of the deployed Vite app).

Converts real recorded trips from the production `data/trips/` directory
into sanitized, browser-friendly JSON files for the hosted Vercel demo.

This script is intentionally NOT run at request time and is NOT bundled into
the demo build. It is run manually to (re)generate every file under
`demo/public/trips/` from the original recordings listed in TRIP_CONFIGS.

It never modifies the source recordings under data/trips/.

Usage (from repo root):
    python demo/scripts/build_demo_trip.py
"""

import json
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
TRIPS_DIR = REPO_ROOT / "data" / "trips"
OUTPUT_DIR = REPO_ROOT / "demo" / "public" / "trips"

# Every trip bundled with the demo. Each entry is converted independently
# and deterministically from its source recording — add an entry here to
# bundle another trip, no other code changes required.
TRIP_CONFIGS = [
    {
        # ~2:36, 0.75 mi, 128 samples, max speed ~31 mph, max RPM ~2973 —
        # a real road-test drive with actual movement and no alarm events
        # (no _events.jsonl file exists for it).
        "trip_id": "2026-09-09_01-21-06",
        "slug": "road-test",
        "label": "Road Test",
    },
    {
        # A real drive with 14 persisted alarm events (9 triggers, 5
        # clears), including an unmatched "High Engine Load" trigger that
        # was still active when the recording ended.
        "trip_id": "2026-09-09_01-11-45",
        "slug": "alarm-event-demo",
        "label": "Alarm Event Demo",
    },
]

# Telemetry fields kept for the demo. Diagnostic/acquisition-health fields
# (sample_duration_ms, sample_rate_hz, missing_values, query_failures,
# connection_status) are stripped as unnecessary for a public playback demo.
SAMPLE_FIELDS = [
    "sequence",
    "timestamp",
    "rpm",
    "speed_mph",
    "load_pct",
    "coolant_temp_f",
    "oil_temp_f",
    "module_voltage_v",
]

# Metadata fields kept for the demo. VIN is never stored by this project's
# trip metadata writer in the first place (only year/make/model), and no
# GPS/location or serial-number fields exist in this schema at all.
METADATA_FIELDS = [
    "start_time",
    "duration_seconds",
    "distance_miles",
    "sample_count",
    "max_speed_mph",
    "max_rpm",
    "average_speed_mph",
    "average_rpm",
    "vehicle",
]

# Alarm event fields kept for the demo. These are persisted verbatim as
# originally recorded — never re-evaluated against today's alarm_rules.json
# and never re-ordered or re-paired here (pairing for display happens
# client-side, at render time, from this same recorded event list).
EVENT_FIELDS = [
    "type",
    "timestamp",
    "sequence",
    "rule",
    "severity",
    "field",
    "operator",
    "threshold",
    "value",
    "duration_seconds",
    "duration_requirement_seconds",
    "reason",
]


def load_jsonl(path):
    items = []

    with open(path, "r", encoding="utf-8") as file:
        for line in file:
            line = line.strip()

            if not line:
                continue

            items.append(json.loads(line))

    return items


def build_trip_json(trip_id):
    metadata_file = TRIPS_DIR / f"trip_{trip_id}_metadata.json"
    trip_file = TRIPS_DIR / f"trip_{trip_id}.jsonl"
    events_file = TRIPS_DIR / f"trip_{trip_id}_events.jsonl"

    with open(metadata_file, "r", encoding="utf-8") as file:
        raw_metadata = json.load(file)

    raw_samples = load_jsonl(trip_file)

    raw_events = (
        load_jsonl(events_file) if events_file.exists() else []
    )

    metadata = {
        field: raw_metadata.get(field)
        for field in METADATA_FIELDS
    }

    samples = [
        {field: sample.get(field) for field in SAMPLE_FIELDS}
        for sample in raw_samples
    ]

    # Keep only the known event fields, but never invent a key that
    # wasn't present on the original persisted event (e.g. older events
    # predate duration_requirement_seconds and simply omit it).
    events = [
        {
            field: event[field]
            for field in EVENT_FIELDS
            if field in event
        }
        for event in raw_events
    ]

    return {
        "metadata": metadata,
        "samples": samples,
        "events": events,
    }


def main():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    for config in TRIP_CONFIGS:
        demo_trip = build_trip_json(config["trip_id"])

        output_file = OUTPUT_DIR / f"{config['slug']}.json"

        with open(output_file, "w", encoding="utf-8") as file:
            json.dump(demo_trip, file, indent=2)
            file.write("\n")

        print(
            f"[{config['slug']}] wrote "
            f"{len(demo_trip['samples'])} samples, "
            f"{len(demo_trip['events'])} events to {output_file}"
        )


if __name__ == "__main__":
    main()
