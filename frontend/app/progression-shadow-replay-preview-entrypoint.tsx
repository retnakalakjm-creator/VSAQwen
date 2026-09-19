"use client";

import type { ChangeEvent } from "react";
import { useState } from "react";

import {
  type AdaptedProgressionShadowReplayDataset,
  adaptProgressionShadowReplayDataset,
} from "./progression-shadow-replay-dataset-adapter";
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
  const [loadedDataset, setLoadedDataset] =
    useState<AdaptedProgressionShadowReplayDataset | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);
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

  const sequences =
    loadedDataset?.sequences ?? progressionShadowReplaySequences;
  const sequence = sequences[sequenceIndex];
  const frame = sequence.frames[cursor];
  const visibleFrames = sequence.frames.slice(0, cursor + 1);
  const sourceLabel =
    loadedDataset?.sourceLabel ??
    PROGRESSION_SHADOW_REPLAY_FIXTURE_BOUNDARY.source;

  function selectSequence(index: number) {
    setSequenceIndex(index);
    setCursor(0);
  }

  async function loadLocalDataset(
    event: ChangeEvent<HTMLInputElement>,
  ) {
    const file = event.target.files?.[0];
    if (!file) {
      return;
    }

    try {
      const parsed: unknown = JSON.parse(await file.text());
      const adapted = adaptProgressionShadowReplayDataset(parsed);
      setLoadedDataset(adapted);
      setLoadError(null);
      setSequenceIndex(0);
      setCursor(0);
    } catch (error) {
      setLoadedDataset(null);
      setSequenceIndex(0);
      setCursor(0);
      setLoadError(
        error instanceof Error
          ? error.message
          : "Unable to read K26 replay dataset",
      );
    } finally {
      event.target.value = "";
    }
  }

  function useSyntheticFallback() {
    setLoadedDataset(null);
    setLoadError(null);
    setSequenceIndex(0);
    setCursor(0);
  }

  return (
    <section
      className="panel progression-shadow-replay-preview"
      data-preview-gate="enabled"
      data-offline-local-artifact-only="true"
      data-network-upload-allowed="false"
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
        Use the built-in synthetic fixtures or explicitly select a frozen K26
        JSON file. Local files are read in browser memory only and are never
        uploaded. Future semantic markers stay hidden until their event bar.
      </p>

      <div
        className="replay-preview-controls"
        aria-label="Offline replay dataset controls"
      >
        <label>
          Load frozen K26 JSON
          <input
            type="file"
            accept=".json,application/json"
            onChange={loadLocalDataset}
          />
        </label>
        <button type="button" onClick={useSyntheticFallback}>
          Use synthetic fixtures
        </button>
      </div>

      {loadError ? (
        <p role="alert">Dataset rejected: {loadError}</p>
      ) : null}

      {loadedDataset ? (
        <dl>
          <div>
            <dt>Basket</dt>
            <dd>{loadedDataset.basketName}</dd>
          </div>
          <div>
            <dt>Sequences</dt>
            <dd>{loadedDataset.sequenceCount}</dd>
          </div>
          <div>
            <dt>Total frames</dt>
            <dd>{loadedDataset.totalFrameCount}</dd>
          </div>
        </dl>
      ) : null}

      <div
        className="replay-preview-controls"
        aria-label="Replay sequence selection"
      >
        <label>
          Sequence
          <select
            value={sequenceIndex}
            onChange={(event) =>
              selectSequence(Number(event.target.value))
            }
          >
            {sequences.map((item, index) => (
              <option key={item.sequence_id} value={index}>
                {item.title}
              </option>
            ))}
          </select>
        </label>
      </div>

      <div
        className="replay-preview-controls"
        aria-label="Replay bar controls"
      >
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
        {sequence.source === "k26-offline-dataset" ? (
          <dl>
            <div>
              <dt>Source event index</dt>
              <dd>{sequence.source_event_bar_index}</dd>
            </div>
            <div>
              <dt>Resolved local weekly index</dt>
              <dd>{sequence.resolved_event_bar_index}</dd>
            </div>
            <div>
              <dt>Event week identity</dt>
              <dd>{sequence.event_week}</dd>
            </div>
          </dl>
        ) : null}
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
          <dt>Replay source</dt>
          <dd>{sourceLabel}</dd>
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
