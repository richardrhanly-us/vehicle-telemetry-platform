import { formatMetricValue, getFieldMeta } from "../utils/telemetry";
import type { ChartableField } from "../types/telemetry";

interface MetricCardProps {
  field: ChartableField;
  value: number | null | undefined;
}

export function MetricCard({ field, value }: MetricCardProps) {
  const meta = getFieldMeta(field);

  if (!meta) {
    return null;
  }

  return (
    <article className={`metric-card ${meta.category}`}>
      <span>{meta.label}</span>
      <strong>{formatMetricValue(field, value)}</strong>
    </article>
  );
}
