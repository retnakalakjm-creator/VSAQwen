"use client";

import type {
  EffortResultReplayFrame,
  EffortResultReplaySequence,
  EffortResultShadowMarker,
} from "./effort-result-replay-bar";

type JsonObject = Record<string, unknown>;
type ReplayNumeric = number | string | undefined;

export const EFFORT_RESULT_REPLAY_DATASET_ADAPTER_BOUNDARY = {
  readOnlyAdapterOnly: true,
  consumesProvidedJsonOnly: true,
  liveApiFetchAllowed: false,
  routeActivationAllowed: false,
  productionSignalAllowed: false,
  scoringAllowed: false,
  rankingAllowed: false,
  actionabilityAllowed: false,
  detectorActivationAllowed: false,
  scannerStateAllowed: false,
  persistenceAllowed: false,
  brokerOrOrderAllowed: false,
} as const;

const DISABLED_MARKER_PRODUCTION_FLAGS = {
  include_in_scoring: false,
  include_in_ranking: false,
  include_in_actionability: false,
  activate_detector: false,
  api_visible: false,
  frontend_visible: false,
  production_change_allowed: false,
} as const;

export type EffortResultShadowReplayDatasetInput = {
  report_type?: unknown;
  replay_dataset_status?: unknown;
  replay_sequences?: unknown;
};

function asRecord(value: unknown): JsonObject | null {
  return value !== null && typeof value === "object" && !Array.isArray(value) ? (value as JsonObject) : null;
}

function asString(value: unknown): string;
function asString(value: unknown, fallback: string): string;
function asString(value: unknown, fallback: undefined): string | undefined;
function asString(value: unknown, fallback: string | undefined = ""): string | undefined {
  return typeof value === "string" ? value : fallback;
}

function asNumberOrString(value: unknown, fallback: ReplayNumeric = 0): ReplayNumeric {
  if (typeof value === "number" || typeof value === "string") return value;
  return fallback;
}

function asBoolean(value: unknown, fallback = false): boolean {
  return typeof value === "boolean" ? value : fallback;
}

function asStringArray(value: unknown): string[] | undefined {
  if (!Array.isArray(value)) return undefined;
  return value.filter((item): item is string => typeof item === "string");
}

function adaptShadowMarker(value: unknown): EffortResultShadowMarker | null {
  const marker = asRecord(value);
  if (!marker) return null;

  return {
    ...DISABLED_MARKER_PRODUCTION_FLAGS,
    target: asString(marker.target),
    symbol: asString(marker.symbol),
    bar_index: Number(asNumberOrString(marker.bar_index, 0)),
    week_beginning: asString(marker.week_beginning),
    shadow_signal_role: asString(marker.shadow_signal_role),
    observation_status: asString(marker.observation_status),
    relationship: asString(marker.relationship, undefined),
    effort_result_candidate: asString(marker.effort_result_candidate, undefined),
    event_labels: asStringArray(marker.event_labels),
  };
}

function adaptReplayFrame(value: unknown): EffortResultReplayFrame | null {
  const frame = asRecord(value);
  if (!frame) return null;

  const shadowMarker = adaptShadowMarker(frame.shadow_marker);
  const hasShadowMarker = Boolean(shadowMarker) && asBoolean(frame.has_shadow_marker, true);

  return {
    bar_index: Number(asNumberOrString(frame.bar_index, 0)),
    replay_offset: Number(asNumberOrString(frame.replay_offset, 0)),
    week_beginning: asString(frame.week_beginning),
    open: asNumberOrString(frame.open, 0) ?? 0,
    high: asNumberOrString(frame.high, 0) ?? 0,
    low: asNumberOrString(frame.low, 0) ?? 0,
    close: asNumberOrString(frame.close, 0) ?? 0,
    volume: asNumberOrString(frame.volume, undefined),
    volume_ratio: asNumberOrString(frame.volume_ratio, undefined),
    spread_ratio: asNumberOrString(frame.spread_ratio, undefined),
    relationship: asString(frame.relationship, undefined),
    effort_result_candidate: asString(frame.effort_result_candidate, undefined),
    is_event_bar: asBoolean(frame.is_event_bar),
    has_shadow_marker: hasShadowMarker,
    shadow_marker: shadowMarker,
  };
}

function adaptReplaySequence(value: unknown): EffortResultReplaySequence | null {
  const sequence = asRecord(value);
  if (!sequence) return null;

  const frames = Array.isArray(sequence.frames)
    ? sequence.frames.map(adaptReplayFrame).filter((frame): frame is EffortResultReplayFrame => frame !== null)
    : [];

  if (frames.length === 0) return null;

  return {
    sequence_id: asString(sequence.sequence_id),
    target: asString(sequence.target),
    symbol: asString(sequence.symbol),
    event_bar_index: Number(asNumberOrString(sequence.event_bar_index, 0)),
    event_week_beginning: asString(sequence.event_week_beginning),
    shadow_signal_role: asString(sequence.shadow_signal_role),
    frame_count: Number(asNumberOrString(sequence.frame_count, frames.length)),
    frames,
  };
}

export function adaptEffortResultShadowReplayDataset(
  report: EffortResultShadowReplayDatasetInput | JsonObject | null | undefined,
): EffortResultReplaySequence[] {
  const source = asRecord(report);
  if (!source || !Array.isArray(source.replay_sequences)) return [];

  return source.replay_sequences
    .map(adaptReplaySequence)
    .filter((sequence): sequence is EffortResultReplaySequence => sequence !== null);
}

export function isEffortResultShadowReplayDatasetReady(
  report: EffortResultShadowReplayDatasetInput | JsonObject | null | undefined,
): boolean {
  const source = asRecord(report);
  return source?.report_type === "effort_result_shadow_replay_dataset" && source?.replay_dataset_status === "shadow_replay_dataset_ready";
}
