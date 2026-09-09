import type { PlaybackSpeed, PlaybackState } from "../hooks/useTelemetryPlayback";
import { formatElapsedSeconds } from "../utils/telemetry";

const SPEED_OPTIONS: PlaybackSpeed[] = [0.5, 1, 2, 5];

interface PlaybackControlsProps {
  playbackState: PlaybackState;
  speed: PlaybackSpeed;
  elapsedSeconds: number;
  totalSeconds: number;
  progressPercent: number;
  onPlay: () => void;
  onPause: () => void;
  onResume: () => void;
  onSpeedChange: (speed: PlaybackSpeed) => void;
}

export function PlaybackControls({
  playbackState,
  speed,
  elapsedSeconds,
  totalSeconds,
  progressPercent,
  onPlay,
  onPause,
  onResume,
  onSpeedChange,
}: PlaybackControlsProps) {
  return (
    <section className="playback-panel">
      <button
        type="button"
        onClick={onPlay}
        disabled={playbackState === "playing" || playbackState === "paused"}
      >
        ▶ Play
      </button>

      <button
        type="button"
        onClick={onPause}
        disabled={playbackState !== "playing"}
      >
        ❚❚ Pause
      </button>

      <button
        type="button"
        onClick={onResume}
        disabled={playbackState !== "paused"}
      >
        ▶ Resume
      </button>

      <label>
        Speed
        <select
          value={speed}
          onChange={(event) =>
            onSpeedChange(Number(event.target.value) as PlaybackSpeed)
          }
        >
          {SPEED_OPTIONS.map((option) => (
            <option key={option} value={option}>
              {option}x
            </option>
          ))}
        </select>
      </label>

      <div className="progress-shell">
        <div className="progress-bar" style={{ width: `${progressPercent}%` }} />
      </div>

      <span className="time-display">
        {formatElapsedSeconds(elapsedSeconds)} /{" "}
        {formatElapsedSeconds(totalSeconds)}
      </span>
    </section>
  );
}
