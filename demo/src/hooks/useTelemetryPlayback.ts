import { useCallback, useEffect, useRef, useState } from "react";
import type { TelemetrySample } from "../types/telemetry";

export type PlaybackSpeed = 0.5 | 1 | 2 | 5;
export type PlaybackState = "idle" | "playing" | "paused" | "completed";

export interface TelemetryPlayback {
  currentIndex: number;
  currentSample: TelemetrySample | null;
  playbackState: PlaybackState;
  speed: PlaybackSpeed;
  elapsedSeconds: number;
  totalSeconds: number;
  progressPercent: number;
  play: () => void;
  pause: () => void;
  resume: () => void;
  setSpeed: (speed: PlaybackSpeed) => void;
}

function sampleTimeMs(sample: TelemetrySample): number {
  return new Date(sample.timestamp).getTime();
}

/**
 * Drives client-side playback of a recorded telemetry sample array.
 *
 * Timing between samples uses the samples' own recorded timestamps
 * (scaled by the current speed) rather than a fixed interval, so
 * playback reflects the real cadence of the original recording.
 *
 * A single chained setTimeout (cleaned up on every dependency change,
 * including a speed change) drives advancement — this avoids duplicate
 * timers, stale closures, and is safe under React StrictMode's
 * mount/cleanup/mount double-invoke in development.
 *
 * This hook assumes `samples` is stable for the lifetime of the
 * component instance that calls it — the caller is expected to mount a
 * fresh instance (e.g. via a `key` keyed on the selected trip's id) when
 * switching to a different recorded trip, rather than passing a new
 * `samples` array into a still-mounted instance. That gives a clean,
 * guaranteed reset (index 0, idle state, no leftover timer) for free
 * through React's normal unmount/mount lifecycle, without needing to
 * diff `samples` by hand inside the hook.
 */
export function useTelemetryPlayback(
  samples: TelemetrySample[],
): TelemetryPlayback {
  const [currentIndex, setCurrentIndex] = useState(0);
  // Raw state only ever holds "idle" | "playing" | "paused". "completed"
  // is derived below from raw state + position, rather than being set
  // synchronously from inside the scheduling effect.
  const [rawState, setRawState] = useState<
    Exclude<PlaybackState, "completed">
  >("idle");
  const [speed, setSpeed] = useState<PlaybackSpeed>(1);

  const timeoutRef = useRef<number | null>(null);

  const reachedEnd =
    samples.length > 0 && currentIndex >= samples.length - 1;

  const playbackState: PlaybackState =
    rawState === "playing" && reachedEnd ? "completed" : rawState;

  useEffect(() => {
    if (rawState !== "playing" || samples.length === 0) {
      return;
    }

    if (currentIndex >= samples.length - 1) {
      return;
    }

    const current = samples[currentIndex];
    const next = samples[currentIndex + 1];

    const rawDelayMs = sampleTimeMs(next) - sampleTimeMs(current);
    const safeDelayMs = Number.isFinite(rawDelayMs) && rawDelayMs > 0
      ? rawDelayMs
      : 0;

    const scaledDelayMs = safeDelayMs / speed;

    timeoutRef.current = window.setTimeout(() => {
      timeoutRef.current = null;
      setCurrentIndex((index) => index + 1);
    }, scaledDelayMs);

    return () => {
      if (timeoutRef.current !== null) {
        window.clearTimeout(timeoutRef.current);
        timeoutRef.current = null;
      }
    };
  }, [rawState, currentIndex, speed, samples]);

  const play = useCallback(() => {
    if (samples.length === 0) {
      return;
    }

    setCurrentIndex(0);
    setRawState("playing");
  }, [samples.length]);

  const pause = useCallback(() => {
    setRawState((state) => (state === "playing" ? "paused" : state));
  }, []);

  const resume = useCallback(() => {
    setRawState((state) => (state === "paused" ? "playing" : state));
  }, []);

  const currentSample = samples[currentIndex] ?? null;
  const firstSample = samples[0] ?? null;
  const lastSample = samples[samples.length - 1] ?? null;

  const elapsedSeconds =
    currentSample && firstSample
      ? (sampleTimeMs(currentSample) - sampleTimeMs(firstSample)) / 1000
      : 0;

  const totalSeconds =
    firstSample && lastSample
      ? (sampleTimeMs(lastSample) - sampleTimeMs(firstSample)) / 1000
      : 0;

  const progressPercent =
    totalSeconds > 0
      ? Math.min(100, (elapsedSeconds / totalSeconds) * 100)
      : 0;

  return {
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
  };
}
