import { AlarmTimeline } from "./AlarmTimeline";
import { MetricCard } from "./MetricCard";
import { PlaybackControls } from "./PlaybackControls";
import { TelemetryCharts } from "./TelemetryCharts";
import { useTelemetryPlayback } from "../hooks/useTelemetryPlayback";
import type { DemoTrip } from "../types/telemetry";

interface TripPlaybackSectionProps {
  trip: DemoTrip;
}

/**
 * Renders playback controls, live metric cards, telemetry charts, and the
 * alarm timeline for one loaded trip.
 *
 * The parent mounts this with a `key` tied to the selected trip's id, so
 * switching trips unmounts the previous instance (tearing down its
 * playback timer via the hook's normal effect cleanup) and mounts a
 * fresh one at index 0 — rather than this component ever receiving a
 * different `trip` prop mid-lifetime.
 */
export function TripPlaybackSection({ trip }: TripPlaybackSectionProps) {
  const samples = trip.samples;

  const {
    currentIndex,
    currentSample,
    playbackState,
    speed,
    elapsedSeconds,
    totalSeconds,
    progressPercent,
    play,
    pause,
    resume,
    setSpeed,
  } = useTelemetryPlayback(samples);

  return (
    <>
      <PlaybackControls
        playbackState={playbackState}
        speed={speed}
        elapsedSeconds={elapsedSeconds}
        totalSeconds={totalSeconds}
        progressPercent={progressPercent}
        onPlay={play}
        onPause={pause}
        onResume={resume}
        onSpeedChange={setSpeed}
      />

      <section className="metric-grid">
        <MetricCard field="rpm" value={currentSample?.rpm} />
        <MetricCard field="speed_mph" value={currentSample?.speed_mph} />
        <MetricCard field="load_pct" value={currentSample?.load_pct} />
        <MetricCard
          field="coolant_temp_f"
          value={currentSample?.coolant_temp_f}
        />
        <MetricCard field="oil_temp_f" value={currentSample?.oil_temp_f} />
        <MetricCard
          field="module_voltage_v"
          value={currentSample?.module_voltage_v}
        />
      </section>

      <section className="demo-columns">
        <div className="chart-panel">
          <div className="panel-heading">
            <p className="panel-label">Telemetry</p>
            <h2>Recorded Session</h2>
          </div>

          <TelemetryCharts samples={samples} currentIndex={currentIndex} />
        </div>

        <div className="event-panel">
          <div className="panel-heading">
            <p className="panel-label">Events</p>
            <h2>Alarm Timeline</h2>
          </div>

          <AlarmTimeline
            events={trip.events}
            tripStartTime={trip.metadata.start_time}
          />
        </div>
      </section>
    </>
  );
}
