import {
  CategoryScale,
  Chart as ChartJS,
  Legend,
  LinearScale,
  LineElement,
  PointElement,
  Tooltip,
  type ChartData,
  type ChartOptions,
  type Plugin,
} from "chart.js";
import { Line } from "react-chartjs-2";
import type { ChartableField, TelemetrySample } from "../types/telemetry";
import { FIELD_META, formatFieldValueWithUnit } from "../utils/telemetry";

ChartJS.register(
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  Tooltip,
  Legend,
);

interface TelemetryChartsProps {
  samples: TelemetrySample[];
  currentIndex: number;
}

function buildChartData(
  field: ChartableField,
  samples: TelemetrySample[],
  currentIndex: number,
  color: string,
): ChartData<"line", (number | null)[], number> {
  const pointRadius = samples.map((_, index) =>
    index === currentIndex ? 5 : 0,
  );

  const pointBackgroundColor = samples.map(() => color);

  return {
    labels: samples.map((sample) => sample.sequence),
    datasets: [
      {
        data: samples.map((sample) => sample[field]),
        borderColor: color,
        backgroundColor: color,
        borderWidth: 2,
        pointRadius,
        pointHoverRadius: 4,
        pointBackgroundColor,
        pointBorderColor: "#0b1627",
        pointBorderWidth: 1,
        tension: 0.25,
      },
    ],
  };
}

function buildChartOptions(field: ChartableField): ChartOptions<"line"> {
  return {
    responsive: true,
    maintainAspectRatio: false,
    animation: false,
    interaction: {
      mode: "index",
      intersect: false,
    },
    plugins: {
      legend: { display: false },
      tooltip: {
        callbacks: {
          label: (context) => {
            const value = context.parsed.y;
            return formatFieldValueWithUnit(field, value);
          },
        },
      },
    },
    scales: {
      x: {
        ticks: { color: "#7f93ad", maxTicksLimit: 6 },
        grid: { color: "#1c2b40" },
      },
      y: {
        ticks: { color: "#7f93ad" },
        grid: { color: "#1c2b40" },
      },
    },
  };
}

/**
 * Draws a dashed vertical cursor at the sample index currently being
 * played back, synchronized with playback state one level up.
 */
function createCurrentIndexPlugin(index: number): Plugin<"line"> {
  return {
    id: "currentIndexCursor",
    afterDraw(chart) {
      const meta = chart.getDatasetMeta(0);
      const point = meta.data[index];

      if (!point || !chart.chartArea) {
        return;
      }

      const { ctx, chartArea } = chart;

      ctx.save();
      ctx.beginPath();
      ctx.moveTo(point.x, chartArea.top);
      ctx.lineTo(point.x, chartArea.bottom);
      ctx.lineWidth = 1.5;
      ctx.strokeStyle = "rgba(248, 250, 252, 0.5)";
      ctx.setLineDash([4, 4]);
      ctx.stroke();
      ctx.restore();
    },
  };
}

export function TelemetryCharts({
  samples,
  currentIndex,
}: TelemetryChartsProps) {
  if (samples.length === 0) {
    return (
      <div className="chart-placeholder">
        No recorded samples available.
      </div>
    );
  }

  return (
    <div className="chart-grid">
      {FIELD_META.map((meta) => (
        <div key={meta.field} className={`chart-card ${meta.category}`}>
          <div className="chart-card-heading">
            <span className="chart-card-title">{meta.label}</span>
            <span className="chart-card-unit">{meta.unit}</span>
          </div>

          <div className="chart-card-canvas">
            <Line
              data={buildChartData(
                meta.field,
                samples,
                currentIndex,
                meta.color,
              )}
              options={buildChartOptions(meta.field)}
              plugins={[createCurrentIndexPlugin(currentIndex)]}
            />
          </div>
        </div>
      ))}
    </div>
  );
}
