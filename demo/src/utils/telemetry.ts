import type {
  AlarmEvent,
  ChartableField,
  TelemetrySample,
  VehicleInfo,
} from "../types/telemetry";

export type MetricCategory = "powertrain" | "thermal" | "electrical";

export interface FieldMeta {
  field: ChartableField;
  label: string;
  unit: string;
  category: MetricCategory;
  color: string;
}

/**
 * Single source of truth mapping a recorded telemetry field to its
 * display label, unit, category color, and chart identity. Metric
 * cards, chart panels, and alarm formatting all read from this list
 * instead of hard-coding field names in multiple places.
 */
export const FIELD_META: FieldMeta[] = [
  {
    field: "rpm",
    label: "Engine Speed",
    unit: "RPM",
    category: "powertrain",
    color: "#38bdf8",
  },
  {
    field: "speed_mph",
    label: "Vehicle Speed",
    unit: "mph",
    category: "powertrain",
    color: "#38bdf8",
  },
  {
    field: "load_pct",
    label: "Engine Load",
    unit: "%",
    category: "powertrain",
    color: "#38bdf8",
  },
  {
    field: "coolant_temp_f",
    label: "Coolant Temperature",
    unit: "°F",
    category: "thermal",
    color: "#fb923c",
  },
  {
    field: "oil_temp_f",
    label: "Oil Temperature",
    unit: "°F",
    category: "thermal",
    color: "#fb923c",
  },
  {
    field: "module_voltage_v",
    label: "Module Voltage",
    unit: "V",
    category: "electrical",
    color: "#a78bfa",
  },
];

const FIELD_META_BY_FIELD = new Map(
  FIELD_META.map((meta) => [meta.field, meta]),
);

export function getFieldMeta(field: string): FieldMeta | undefined {
  return FIELD_META_BY_FIELD.get(field as ChartableField);
}

export function formatMake(make: string | null | undefined): string {
  if (!make) {
    return "";
  }

  return make
    .toLowerCase()
    .replace(/\b\w/g, (character) => character.toUpperCase());
}

export function formatVehicleName(
  vehicle: VehicleInfo | null | undefined,
): string {
  if (!vehicle || !vehicle.year || !vehicle.make || !vehicle.model) {
    return "Unknown Vehicle";
  }

  return `${vehicle.year} ${formatMake(vehicle.make)} ${vehicle.model}`;
}

export function formatMetricValue(
  field: ChartableField,
  value: number | null | undefined,
): string {
  if (value === null || value === undefined || Number.isNaN(value)) {
    return "--";
  }

  const meta = getFieldMeta(field);
  const unit = meta ? meta.unit : "";

  return unit ? `${value} ${unit}` : `${value}`;
}

export function formatElapsedSeconds(seconds: number): string {
  const safeSeconds = Math.max(0, Math.round(seconds));
  const minutes = Math.floor(safeSeconds / 60);
  const remainingSeconds = safeSeconds % 60;

  return (
    String(minutes).padStart(2, "0") +
    ":" +
    String(remainingSeconds).padStart(2, "0")
  );
}

export function computeElapsedLabel(
  eventTimestamp: string | null | undefined,
  tripStartTimestamp: string | null | undefined,
): string | null {
  if (!eventTimestamp || !tripStartTimestamp) {
    return null;
  }

  const elapsedMs =
    new Date(eventTimestamp).getTime() -
    new Date(tripStartTimestamp).getTime();

  if (Number.isNaN(elapsedMs)) {
    return null;
  }

  return formatElapsedSeconds(elapsedMs / 1000);
}

export function formatFieldValueWithUnit(
  field: string,
  value: number | null | undefined,
): string {
  if (value === null || value === undefined) {
    return "N/A";
  }

  const meta = getFieldMeta(field);

  return meta ? `${value}${meta.unit}` : `${value}`;
}

export function getSampleElapsedSeconds(
  sample: TelemetrySample,
  tripStartTimestamp: string | null | undefined,
): number {
  if (!tripStartTimestamp) {
    return 0;
  }

  const elapsedMs =
    new Date(sample.timestamp).getTime() -
    new Date(tripStartTimestamp).getTime();

  return Number.isNaN(elapsedMs) ? 0 : elapsedMs / 1000;
}

export interface AlarmGroup {
  rule: string;
  triggered: AlarmEvent | null;
  cleared: AlarmEvent | null;
}

/**
 * Pairs a "triggered" event with its later matching "cleared" event for
 * the same rule, in recorded order. The alarm engine only tracks one
 * open occurrence per rule at a time, so first-in-first-out pairing per
 * rule name is reliable and never guesses at a pairing.
 */
export function pairAlarmEvents(events: AlarmEvent[]): AlarmGroup[] {
  const sorted = [...events].sort(
    (a, b) => (a.sequence ?? 0) - (b.sequence ?? 0),
  );

  const openByRule = new Map<string, AlarmGroup>();
  const groups: AlarmGroup[] = [];

  for (const event of sorted) {
    const ruleName = event.rule ?? "Alarm";

    if (event.type === "cleared") {
      const open = openByRule.get(ruleName);

      if (open) {
        open.cleared = event;
        openByRule.delete(ruleName);
        continue;
      }

      groups.push({ rule: ruleName, triggered: null, cleared: event });
      continue;
    }

    const group: AlarmGroup = {
      rule: ruleName,
      triggered: event,
      cleared: null,
    };

    openByRule.set(ruleName, group);
    groups.push(group);
  }

  return groups;
}
