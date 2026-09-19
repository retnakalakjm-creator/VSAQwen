"use client";

import { useState } from "react";

import {
  PROGRESSION_SHADOW_REPLAY_FIXTURE_BOUNDARY,
  progressionShadowReplaySequences,
} from "./progression-shadow-replay-fixtures";
import {
  PROGRESSION_SHADOW_REPLAY_PREVIEW_GATE,
  evaluateProgressionShadowReplayPreviewGate,
} from "./progression-shadow-replay-preview-gate";

type ProgressionShadowReplayPreviewEntrypointProps = {
  enableOfflinePreview?: boolean;
};

export function ProgressionShadowReplayPreviewEntrypoint({
  enableOfflinePreview = false,
}: ProgressionShadowReplayPreviewEntrypointProps) {
  const gate = evaluateProgressionShadowReplayPreviewGate({
    enableOfflinePreview,
  });
  const [sequenceIndex, setSequenceIndex] = useState(0);
  const [cursor, setCursor] = useState(0);

  if (!gate.enabled || !gate.canRenderPreview) {
    return (
      <section
        className="panel progression-shadow-replay-preview"
        data-preview-gate="disabled"
        data-production-change-allowed="false"
      >
        <span className="section-kicker">SHADOW PREVIEW CLOSED</span>
        <p>
          The progression semantic replay preview is disabled outside the
          explicit dev-only offline route.
        </p>
      </section>
    );
  }

  const sequence = progressionShadowReplaySequences[sequenceIndex];
  const frame = sequence.frames[cursor];
  const visibleFrames = sequence.frames.slice(0, cursor + 1);

  function selectSequence(index: number) {
    setSequenceIndex(index);
    setCursor(0);
  }

  return (
    <section
      className="panel progression-shadow-replay-preview"
      data-preview-gate="enabled"
      data-synthetic-fixture-only="true"
      data-live-api-fetch-allowed="false"
      data-production-change-allowed="false"
      data-qualification-mutation-allowed="false"
      data-actionability-allowed="false"
    >
      <div className="workspace-heading">
        <div>
          <span className="section-kicker">SHADOW SEMANTIC REPLAY</span>
          <h2>Progression transition-warning preview</h2>
        </div>
        <span>
          bar {cursor + 1} / {sequence.frames.length}
        </span>
      </div>

      <p>
        Synthetic weekly bars only. Semantic markers become visible only when
        the replay reaches their event bar. No future marker is exposed early.
      </p>

      <div className="replay-preview-controls" aria-label="Replay sequence selection">
        {progressionShadowReplaySequences.map((item, index) => (
          <button
            key={item.sequence_id}
            type="button"
            onClick={() => selectSequence(index)}
            aria-pressed={sequenceIndex === index}
          >
            {item.title}
          </button>
        ))}
      </div>

      <div className="replay-preview-controls" aria-label="Replay bar controls">
        <button
          type="button"
          onClick={() => setCursor((value) => Math.max(0, value - 1))}
          disabled={cursor === 0}
        >
          Previous bar
        </button>
        <button
          type="button"
          onClick={() =>
            setCursor((value) =>
              Math.min(sequence.frames.length - 1, value + 1),
            )
          }
          disabled={cursor === sequence.frames.length - 1}
        >
          Next bar
        </button>
        <button type="button" onClick={() => setCursor(0)}>
          Reset
        </button>
      </div>

      <section aria-label="Current replay frame">
        <h3>{sequence.title}</h3>
        <p>{sequence.description}</p>
        <dl>
          <div>
            <dt>Week</dt>
            <dd>{frame.week}</dd>
          </div>
          <div>
            <dt>OHLC</dt>
            <dd>
              {frame.open} / {frame.high} / {frame.low} / {frame.close}
            </dd>
          </div>
          <div>
            <dt>Volume</dt>
            <dd>{frame.volume}</dd>
          </div>
          <div>
            <dt>Semantic marker</dt>
            <dd>{frame.semantic_role ?? "none"}</dd>
          </div>
          <div>
            <dt>Warning direction</dt>
            <dd>{frame.projected_transition_direction ?? "none"}</dd>
          </div>
        </dl>
      </section>

      <table>
        <thead>
          <tr>
            <th>Bar</th>
            <th>Week</th>
            <th>Close</th>
            <th>Event</th>
            <th>Shadow role</th>
          </tr>
        </thead>
        <tbody>
          {visibleFrames.map((item) => (
            <tr key={item.bar_index}>
              <td>{item.bar_index}</td>
              <td>{item.week}</td>
              <td>{item.close}</td>
              <td>{item.is_event_bar ? "yes" : "no"}</td>
              <td>{item.semantic_role ?? "—"}</td>
            </tr>
          ))}
        </tbody>
      </table>

      <dl>
        <div>
          <dt>Fixture source</dt>
          <dd>{PROGRESSION_SHADOW_REPLAY_FIXTURE_BOUNDARY.source}</dd>
        </div>
        <div>
          <dt>Preview gate default</dt>
          <dd>
            {PROGRESSION_SHADOW_REPLAY_PREVIEW_GATE.enabledByDefault
              ? "enabled"
              : "disabled"}
          </dd>
        </div>
        <div>
          <dt>Reversal confirmed</dt>
          <dd>no</dd>
        </div>
        <div>
          <dt>Persistent direction claim</dt>
          <dd>no</dd>
        </div>
        <div>
          <dt>Production effect</dt>
          <dd>none</dd>
        </div>
      </dl>
    </section>
  );
}
