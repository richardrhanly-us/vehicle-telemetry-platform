export interface VehicleInfo {
  year: string | number | null;
  make: string | null;
  model: string | null;
}

export interface TripMetadata {
  start_time: string | null;
  duration_seconds: number | null;
  distance_miles: number | null;
  sample_count: number | null;
  max_speed_mph: number | null;
  max_rpm: number | null;
  average_speed_mph: number | null;
  average_rpm: number | null;
  vehicle: VehicleInfo | null;
}

/**
 * Matches the sanitized fields written by demo/scripts/build_demo_trip.py
 * from a real recorded TelemetrySample (telemetry/models.py).
 */
export interface TelemetrySample {
  sequence: number;
  timestamp: string;
  rpm: number | null;
  speed_mph: number | null;
  load_pct: number | null;
  coolant_temp_f: number | null;
  oil_temp_f: number | null;
  module_voltage_v: number | null;
}

export type ChartableField = Exclude<
  keyof TelemetrySample,
  "sequence" | "timestamp"
>;

export type AlarmEventType = "triggered" | "cleared";

/**
 * Matches the persisted alarm event shape produced by
 * telemetry/alarms.py AlarmEngine._build_event().
 */
export interface AlarmEvent {
  type: AlarmEventType;
  timestamp: string;
  sequence: number | null;
  rule: string;
  severity: string;
  field: string;
  operator: string;
  threshold: number | null;
  value: number | null;
  duration_seconds: number;
  duration_requirement_seconds?: number;
  reason?: string;
}

export interface DemoTrip {
  metadata: TripMetadata;
  samples: TelemetrySample[];
  events: AlarmEvent[];
}
