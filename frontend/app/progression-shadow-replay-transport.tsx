"use client";

import { useEffect } from "react";

type ProgressionShadowReplayTransportProps = {
  cursor: number;
  frameCount: number;
  isPlaying: boolean;
  speedMs: number;
  onCursorChange: (cursor: number) => void;
  onPlayingChange: (isPlaying: boolean) => void;
  onSpeedChange: (speedMs: number) => void;
};

const SPEED_OPTIONS = [
  { label: "0.5×", value: 1400 },
  { label: "1×", value: 700 },
  { label: "2×", value: 350 },
] as const;

export function ProgressionShadowReplayTransport({
  cursor,
  frameCount,
  isPlaying,
  speedMs,
  onCursorChange,
  onPlayingChange,
  onSpeedChange,
}: ProgressionShadowReplayTransportProps) {
  const lastCursor = Math.max(0, frameCount - 1);
  const atStart = cursor <= 0;
  const atEnd = cursor >= lastCursor;

  useEffect(() => {
    if (!isPlaying) {
      return;
    }

    if (atEnd) {
      onPlayingChange(false);
      return;
    }

    const timer = window.setTimeout(() => {
      onCursorChange(Math.min(lastCursor, cursor + 1));
    }, speedMs);

    return () => {
      window.clearTimeout(timer);
    };
  }, [
    atEnd,
    cursor,
    isPlaying,
    lastCursor,
    onCursorChange,
    onPlayingChange,
    speedMs,
  ]);

  function reset() {
    onPlayingChange(false);
    onCursorChange(0);
  }

  function stepPrevious() {
    onPlayingChange(false);
    onCursorChange(Math.max(0, cursor - 1));
  }

  function stepNext() {
    onPlayingChange(false);
    onCursorChange(Math.min(lastCursor, cursor + 1));
  }

  function togglePlaying() {
    if (atEnd) {
      onCursorChange(0);
      onPlayingChange(true);
      return;
    }
    onPlayingChange(!isPlaying);
  }

  function scrub(value: number) {
    onPlayingChange(false);
    onCursorChange(
      Math.min(lastCursor, Math.max(0, Math.trunc(value))),
    );
  }

  return (
    <section
      className="progression-replay-transport"
      aria-label="Replay transport"
      data-causal-cursor-only="true"
      data-future-bars-allowed="false"
      data-live-api-fetch-allowed="false"
      data-production-effect="none"
    >
      <div className="progression-replay-transport-buttons">
        <button type="button" onClick={reset} disabled={atStart}>
          Reset
        </button>
        <button
          type="button"
          onClick={stepPrevious}
          disabled={atStart}
          aria-label="Previous replay bar"
        >
          ◀
        </button>
        <button
          type="button"
          onClick={togglePlaying}
          aria-label={isPlaying ? "Pause replay" : "Play replay"}
        >
          {isPlaying ? "Pause" : atEnd ? "Replay" : "Play"}
        </button>
        <button
          type="button"
          onClick={stepNext}
          disabled={atEnd}
          aria-label="Next replay bar"
        >
          ▶
        </button>
      </div>

      <label className="progression-replay-position">
        <span>
          Bar {cursor + 1} / {frameCount}
        </span>
        <input
          type="range"
          min={0}
          max={lastCursor}
          step={1}
          value={cursor}
          onChange={(event) => scrub(Number(event.target.value))}
          aria-label="Replay position"
        />
      </label>

      <label className="progression-replay-speed">
        <span>Speed</span>
        <select
          value={speedMs}
          onChange={(event) =>
            onSpeedChange(Number(event.target.value))
          }
          aria-label="Replay speed"
        >
          {SPEED_OPTIONS.map((option) => (
            <option key={option.value} value={option.value}>
              {option.label}
            </option>
          ))}
        </select>
      </label>
    </section>
  );
}
