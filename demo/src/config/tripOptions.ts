export interface TripOption {
  id: string;
  label: string;
  file: string;
}

/**
 * The bundled demo trips. Each `file` corresponds to a sanitized JSON
 * payload under demo/public/trips/, generated deterministically from a
 * real recording by demo/scripts/build_demo_trip.py — keep this list in
 * sync with that script's TRIP_CONFIGS.
 */
export const TRIP_OPTIONS: TripOption[] = [
  {
    id: "road-test",
    label: "Road Test",
    file: "road-test.json",
  },
  {
    id: "alarm-event-demo",
    label: "Alarm Event Demo",
    file: "alarm-event-demo.json",
  },
];

export const DEFAULT_TRIP_ID = "road-test";
