"use client";

import { useMemo, useState } from "react";

export type EffortResultShadowMarker = {
  target: string;
  symbol: string;
  bar_index: number;
  week_beginning: string;
  shadow_signal_role: string;
  observation_status: string;
  relationship?: string;
  effort_result_candidate?: string;
  event_labels?: string[];
  include_in_scoring?: false;
  include_in_ranking?: false;
  include_in_actionability?: false;
  activate_detector?: false;
  api_visible?: false;
  frontend_visible?: false;
  production_change_allowed?: false;
};

export type EffortResultReplayFrame = {
  bar_index: number;
  replay_offset: number;
  week_beginning: string;
  open: number | string;
  high: number | string;
  low: number | string;
  close: number | string;
  volume?: number | string;
  volume_ratio?: number | string;
  spread_ratio?: number | string;
  relationship?: string;
  effort_result_candidate?: string;
  is_event_bar: boolean;
  has_shadow_marker: boolean;
  shadow_marker?: EffortResultShadowMarker | null;
};

export type EffortResultReplaySequence = {
  sequence_id: string;
  target: string;
  symbol: string;
  event_bar_index: number;
  event_week_beginning: string;
  shadow_signal_role: string;
  frame_count: number;
  frames: EffortResultReplayFrame[];
};

export type EffortResultMarkerOverlayTone = "accumulation" | "distribution" | "neutral";

export type EffortResultMarkerOverlay = {
  marker: EffortResultShadowMarker;
  frameIndex: number;
  barIndex: number;
  replayOffset: number;
  lane: number;
  label: string;
  tone: EffortResultMarkerOverlayTone;
};

type PlaybackState = "paused" | "playing";

type EffortResultReplayBarProps = {
  replaySequences: EffortResultReplaySequence[];
  initialSequenceId?: string;
  initialFrameIndex?: number;
  onFrameChange?: (sequence: EffortResultReplaySequence, frame: EffortResultReplayFrame) => void;
  onSequenceChange?: (sequence: EffortResultReplaySequence) => void;
  onPlaybackChange?: (state: PlaybackState) => void;
};

function clampFrameIndex(index: number, frameCount: number) {
  if (frameCount <= 0) return 0;
  return Math.max(0, Math.min(index, frameCount - 1));
}

function displayWeek(value: string | undefined) {
  if (!value) return "—";
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return value;
  return parsed.toLocaleDateString("en-IN", {
    day: "2-digit",
    month: "short",
    year: "numeric",
  });
}

function markerLabel(marker: EffortResultShadowMarker) {
  const firstEvent = marker.event_labels?.[0];
  return firstEvent ?? marker.effort_result_candidate ?? marker.target;
}

export function classifyEffortResultShadowMarker(
  marker: EffortResultShadowMarker | null | undefined,
): EffortResultMarkerOverlayTone {
  if (!marker) return "neutral";
  const evidence = [
    marker.target,
    marker.shadow_signal_role,
    marker.relationship,
    marker.effort_result_candidate,
    ...(marker.event_labels ?? []),
  ]
    .join(" ")
    .toUpperCase();

  if (evidence.includes("SUPPLY") || evidence.includes("NO_DEMAND") || evidence.includes("BEARISH")) {
    return "distribution";
  }
  if (evidence.includes("RESULT_GT_EFFORT") || evidence.includes("DEMAND") || evidence.includes("BULLISH")) {
    return "accumulation";
  }
  return "neutral";
}

export function buildEffortResultMarkerOverlays(
  frames: EffortResultReplayFrame[],
): EffortResultMarkerOverlay[] {
  return frames
    .map((frame, frameIndex) => {
      if (!frame.has_shadow_marker || !frame.shadow_marker) return null;
      return {
        marker: frame.shadow_marker,
        frameIndex,
        barIndex: frame.bar_index,
        replayOffset: frame.replay_offset,
        lane: Math.abs(frame.replay_offset) % 3,
        label: markerLabel(frame.shadow_marker),
        tone: classifyEffortResultShadowMarker(frame.shadow_marker),
      };
    })
    .filter((overlay): overlay is EffortResultMarkerOverlay => overlay !== null);
}

export function EffortResultReplayBar({
  replaySequences,
  initialSequenceId,
  initialFrameIndex = 0,
  onFrameChange,
  onSequenceChange,
  onPlaybackChange,
}: EffortResultReplayBarProps) {
  const firstSequenceId = replaySequences[0]?.sequence_id ?? "";
  const [activeSequenceId, setActiveSequenceId] = useState(initialSequenceId ?? firstSequenceId);
  const [activeFrameIndex, setActiveFrameIndex] = useState(initialFrameIndex);
  const [playbackState, setPlaybackState] = useState<PlaybackState>("paused");

  const activeSequence = useMemo(
    () => replaySequences.find((sequence) => sequence.sequence_id === activeSequenceId) ?? replaySequences[0] ?? null,
    [activeSequenceId, replaySequences],
  );

  const frames = activeSequence?.frames ?? [];
  const safeFrameIndex = clampFrameIndex(activeFrameIndex, frames.length);
  const activeFrame = frames[safeFrameIndex] ?? null;
  const markerOverlays = useMemo(() => buildEffortResultMarkerOverlays(frames), [frames]);
  const activeOverlay = markerOverlays.find((overlay) => overlay.frameIndex === safeFrameIndex) ?? null;

  function publishFrame(index: number) {
    if (!activeSequence || frames.length === 0) return;
    const nextIndex = clampFrameIndex(index, frames.length);
    setActiveFrameIndex(nextIndex);
    onFrameChange?.(activeSequence, frames[nextIndex]);
  }

  function selectSequence(sequenceId: string) {
    const nextSequence = replaySequences.find((sequence) => sequence.sequence_id === sequenceId);
    if (!nextSequence) return;
    setActiveSequenceId(sequenceId);
    setActiveFrameIndex(0);
    setPlaybackState("paused");
    onSequenceChange?.(nextSequence);
    if (nextSequence.frames[0]) onFrameChange?.(nextSequence, nextSequence.frames[0]);
    onPlaybackChange?.("paused");
  }

  function togglePlayback() {
    const nextState: PlaybackState = playbackState === "playing" ? "paused" : "playing";
    setPlaybackState(nextState);
    onPlaybackChange?.(nextState);
  }

  if (replaySequences.length === 0) {
    return (
      <section className="panel effort-result-replay-bar" aria-label="Effort Result replay bar scaffold">
        <span className="section-kicker">SHADOW REPLAY</span>
        <h2>Effort/Result replay bar</h2>
        <p>No shadow replay sequences are loaded. This scaffold does not fetch live data or activate production signals.</p>
      </section>
    );
  }

  return (
    <section className="panel effort-result-replay-bar" aria-label="Effort Result replay bar scaffold">
      <div className="workspace-heading">
        <div>
          <span className="section-kicker">SHADOW REPLAY</span>
          <h2>Effort/Result replay bar</h2>
        </div>
        <span>{activeSequence ? `${safeFrameIndex + 1}/${frames.length}` : "0/0"}</span>
      </div>

      <div className="replay-contract-note" data-production-change-allowed="false">
        Offline visual backtest scaffold only. No API fetch, route activation, scoring, ranking, alerting, or detector activation.
      </div>

      <label>
        Sequence
        <select value={activeSequence?.sequence_id ?? ""} onChange={(event) => selectSequence(event.target.value)}>
          {replaySequences.map((sequence) => (
            <option value={sequence.sequence_id} key={sequence.sequence_id}>
              {sequence.symbol} · {sequence.target} · {displayWeek(sequence.event_week_beginning)}
            </option>
          ))}
        </select>
      </label>

      <div className="replay-controls" role="group" aria-label="Replay controls">
        <button type="button" onClick={() => publishFrame(safeFrameIndex - 1)} disabled={safeFrameIndex <= 0}>
          Previous bar
        </button>
        <button type="button" onClick={togglePlayback} aria-pressed={playbackState === "playing"}>
          {playbackState === "playing" ? "Pause" : "Play"}
        </button>
        <button type="button" onClick={() => publishFrame(safeFrameIndex + 1)} disabled={safeFrameIndex >= frames.length - 1}>
          Next bar
        </button>
      </div>

      <input
        aria-label="Replay scrubber"
        type="range"
        min={0}
        max={Math.max(frames.length - 1, 0)}
        value={safeFrameIndex}
        onChange={(event) => publishFrame(Number(event.target.value))}
      />

      <ol className="shadow-marker-rail" aria-label="Shadow marker rail">
        {frames.map((frame, index) => (
          <li
            key={`${activeSequence?.sequence_id ?? "sequence"}-${frame.bar_index}`}
            data-active={index === safeFrameIndex}
            data-shadow-overlay={frame.has_shadow_marker ? "true" : "false"}
          >
            <button type="button" onClick={() => publishFrame(index)} aria-label={`Replay bar ${frame.bar_index}`}>
              {frame.has_shadow_marker ? "◆" : "•"}
            </button>
          </li>
        ))}
      </ol>

      <ol className="effort-result-shadow-marker-overlay" aria-label="Effort Result shadow marker overlay">
        {markerOverlays.map((overlay) => (
          <li
            key={`${activeSequence?.sequence_id ?? "sequence"}-${overlay.barIndex}-overlay`}
            data-marker-tone={overlay.tone}
            data-marker-lane={overlay.lane}
            data-replay-offset={overlay.replayOffset}
            data-active={overlay.frameIndex === safeFrameIndex}
          >
            <button type="button" onClick={() => publishFrame(overlay.frameIndex)} aria-label={`Shadow marker ${overlay.label}`}>
              <strong>{overlay.label}</strong>
              <span>{displayWeek(overlay.marker.week_beginning)}</span>
            </button>
          </li>
        ))}
      </ol>

      {activeFrame && (
        <article className="replay-frame-metadata">
          <h3>{displayWeek(activeFrame.week_beginning)}</h3>
          <p>Replay offset: {activeFrame.replay_offset}</p>
          <p>Close: {activeFrame.close}</p>
          <p>Volume ratio: {activeFrame.volume_ratio ?? "—"}</p>
          {activeFrame.shadow_marker && <p>Shadow marker: {activeFrame.shadow_marker.shadow_signal_role}</p>}
          {activeOverlay && <p>Overlay tone: {activeOverlay.tone}</p>}
        </article>
      )}
    </section>
  );
}
