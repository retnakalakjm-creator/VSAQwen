import type {
  ProgressionShadowReplayFrame,
  ProgressionShadowReplaySequence,
  ProgressionShadowSemanticRole,
} from "./progression-shadow-replay-fixtures";

export const PROGRESSION_SHADOW_REPLAY_DATASET_AUDIT_ID =
  "progression-shadow-semantic-replay-dataset-v1";

export type AdaptedProgressionShadowReplayDataset = {
  sourceLabel: string;
  basketName: string;
  sourceEventCount: number;
  sequenceCount: number;
  totalFrameCount: number;
  sequences: ProgressionShadowReplaySequence[];
};

type JsonRecord = Record<string, unknown>;

function record(value: unknown, label: string): JsonRecord {
  if (typeof value !== "object" || value === null || Array.isArray(value)) {
    throw new Error(`${label} must be an object`);
  }
  return value as JsonRecord;
}

function stringValue(value: unknown, label: string): string {
  if (typeof value !== "string" || value.length === 0) {
    throw new Error(`${label} must be a non-empty string`);
  }
  return value;
}

function numberValue(value: unknown, label: string): number {
  if (typeof value !== "number" || !Number.isFinite(value)) {
    throw new Error(`${label} must be a finite number`);
  }
  return value;
}

function booleanFalse(value: unknown, label: string): false {
  if (value !== false) {
    throw new Error(`${label} must be false`);
  }
  return false;
}

function semanticRole(value: unknown): ProgressionShadowSemanticRole {
  const role = stringValue(value, "semantic_role");
  const allowed: ProgressionShadowSemanticRole[] = [
    "TRANSITION_WARNING",
    "ALIGNED_PROGRESSION_OBSERVATION",
    "NEUTRAL_PROGRESSION_OBSERVATION",
    "UNKNOWN_TREND_CONTEXT_OBSERVATION",
  ];
  if (!allowed.includes(role as ProgressionShadowSemanticRole)) {
    throw new Error(`unsupported semantic_role: ${role}`);
  }
  return role as ProgressionShadowSemanticRole;
}

function direction(
  value: unknown,
  label: string,
): "bullish" | "bearish" | null {
  if (value === null) {
    return null;
  }
  if (value !== "bullish" && value !== "bearish") {
    throw new Error(`${label} must be bullish, bearish, or null`);
  }
  return value;
}

function alignment(
  value: unknown,
): "opposed" | "aligned" | "neutral" | "unknown" | null {
  if (value === null) {
    return null;
  }
  if (
    value !== "opposed" &&
    value !== "aligned" &&
    value !== "neutral" &&
    value !== "unknown"
  ) {
    throw new Error("trend_alignment is unsupported");
  }
  return value;
}

function adaptFrame(
  value: unknown,
  options: {
    sequenceId: string;
    frameIndex: number;
  },
): ProgressionShadowReplayFrame {
  const { sequenceId, frameIndex } = options;
  const raw = record(value, `${sequenceId} frame ${frameIndex}`);
  const isEventBar = raw.is_event_bar;
  if (typeof isEventBar !== "boolean") {
    throw new Error(`${sequenceId} frame is_event_bar must be boolean`);
  }

  const role = raw.semantic_role === null
    ? null
    : semanticRole(raw.semantic_role);
  const projectedDirection = direction(
    raw.projected_transition_direction,
    "projected_transition_direction",
  );

  booleanFalse(raw.reversal_confirmed, "reversal_confirmed");
  booleanFalse(
    raw.persistent_direction_claim,
    "persistent_direction_claim",
  );
  booleanFalse(raw.affects_qualification, "affects_qualification");
  booleanFalse(raw.affects_scoring, "affects_scoring");
  booleanFalse(raw.is_actionable, "is_actionable");

  const eventDirection = direction(
    raw.event_direction,
    "event_direction",
  );
  const trendAlignment = alignment(raw.trend_alignment);
  if (
    !isEventBar &&
    (
      role !== null ||
      projectedDirection !== null ||
      eventDirection !== null ||
      trendAlignment !== null
    )
  ) {
    throw new Error(
      `${sequenceId} non-event frame contains semantic marker data`,
    );
  }

  return {
    bar_index: numberValue(raw.bar_index, "bar_index"),
    week: stringValue(raw.week, "week"),
    open: numberValue(raw.open, "open"),
    high: numberValue(raw.high, "high"),
    low: numberValue(raw.low, "low"),
    close: numberValue(raw.close, "close"),
    volume: numberValue(raw.volume, "volume"),
    is_event_bar: isEventBar,
    event_direction: eventDirection,
    trend_alignment: trendAlignment,
    semantic_role: role,
    projected_transition_direction: projectedDirection,
    reversal_confirmed: false,
    persistent_direction_claim: false,
    affects_qualification: false,
    affects_scoring: false,
    is_actionable: false,
  };
}

function adaptSequence(
  value: unknown,
  index: number,
): ProgressionShadowReplaySequence {
  const raw = record(value, `replay_sequences[${index}]`);
  const sequenceId = stringValue(raw.sequence_id, "sequence_id");
  if (!Array.isArray(raw.frames) || raw.frames.length === 0) {
    throw new Error(`${sequenceId} must contain replay frames`);
  }

  const frames = raw.frames.map((frame, frameIndex) =>
    adaptFrame(frame, {
      sequenceId,
      frameIndex,
    }),
  );
  const eventFrames = frames.filter((frame) => frame.is_event_bar);
  if (eventFrames.length !== 1) {
    throw new Error(`${sequenceId} must contain exactly one event frame`);
  }

  const symbol = stringValue(raw.symbol, "symbol");
  const eventWeek = stringValue(raw.event_week, "event_week");
  const eventDirection = direction(raw.event_direction, "event_direction");
  if (eventDirection === null) {
    throw new Error(`${sequenceId} event_direction cannot be null`);
  }
  const trendAlignment = alignment(raw.trend_alignment);
  if (trendAlignment === null) {
    throw new Error(`${sequenceId} trend_alignment cannot be null`);
  }
  const role = semanticRole(raw.semantic_role);
  const projectedDirection = direction(
    raw.projected_transition_direction,
    "projected_transition_direction",
  );
  const resolvedEventBarIndex = numberValue(
    raw.resolved_event_bar_index,
    "resolved_event_bar_index",
  );
  const sourceEventBarIndex = numberValue(
    raw.source_event_bar_index,
    "source_event_bar_index",
  );
  const eventFrame = eventFrames[0];

  if (eventFrame.week !== eventWeek) {
    throw new Error(`${sequenceId} event week does not match event frame`);
  }
  if (eventFrame.bar_index !== resolvedEventBarIndex) {
    throw new Error(
      `${sequenceId} resolved event index does not match event frame`,
    );
  }
  if (eventFrame.semantic_role !== role) {
    throw new Error(`${sequenceId} semantic role mismatch`);
  }
  if (eventFrame.event_direction !== eventDirection) {
    throw new Error(`${sequenceId} event direction mismatch`);
  }
  if (eventFrame.trend_alignment !== trendAlignment) {
    throw new Error(`${sequenceId} trend alignment mismatch`);
  }
  if (
    eventFrame.projected_transition_direction !== projectedDirection
  ) {
    throw new Error(`${sequenceId} transition direction mismatch`);
  }
  if (
    role === "TRANSITION_WARNING" &&
    projectedDirection !== eventDirection
  ) {
    throw new Error(
      `${sequenceId} transition warning direction mismatch`,
    );
  }
  if (
    role !== "TRANSITION_WARNING" &&
    projectedDirection !== null
  ) {
    throw new Error(
      `${sequenceId} non-warning sequence has transition direction`,
    );
  }

  return {
    sequence_id: sequenceId,
    title: `${symbol} · ${eventWeek.slice(0, 10)} · ${role}`,
    description:
      `${eventDirection} progression in ${trendAlignment} trend context. ` +
      "Loaded from a frozen K26 offline replay dataset.",
    event_bar_index: resolvedEventBarIndex,
    source: "k26-offline-dataset",
    symbol,
    event_week: eventWeek,
    source_event_bar_index: sourceEventBarIndex,
    resolved_event_bar_index: resolvedEventBarIndex,
    event_direction: eventDirection,
    trend_alignment: trendAlignment,
    semantic_role: role,
    projected_transition_direction: projectedDirection,
    frames,
  };
}

export function adaptProgressionShadowReplayDataset(
  value: unknown,
): AdaptedProgressionShadowReplayDataset {
  const raw = record(value, "K26 replay dataset");
  if (raw.audit_id !== PROGRESSION_SHADOW_REPLAY_DATASET_AUDIT_ID) {
    throw new Error("unsupported K26 replay dataset audit_id");
  }
  if (raw.dataset_status !== "shadow_replay_dataset_ready") {
    throw new Error("K26 replay dataset is not ready");
  }

  booleanFalse(raw.reversal_confirmed, "reversal_confirmed");
  booleanFalse(
    raw.persistent_direction_claim,
    "persistent_direction_claim",
  );
  booleanFalse(raw.affects_qualification, "affects_qualification");
  booleanFalse(raw.affects_scoring, "affects_scoring");
  booleanFalse(raw.is_actionable, "is_actionable");

  const basketName = stringValue(raw.basket_name, "basket_name");
  const sourceEventCount = numberValue(
    raw.source_event_count,
    "source_event_count",
  );
  const sequenceCount = numberValue(raw.sequence_count, "sequence_count");
  if (sequenceCount < 1) {
    throw new Error("sequence_count must be positive");
  }
  const failedSymbolCount = numberValue(
    raw.failed_symbol_count,
    "failed_symbol_count",
  );
  if (failedSymbolCount !== 0) {
    throw new Error("K26 replay dataset contains symbol failures");
  }
  const totalFrameCount = numberValue(
    raw.total_frame_count,
    "total_frame_count",
  );

  if (!Array.isArray(raw.replay_sequences)) {
    throw new Error("replay_sequences must be an array");
  }
  if (raw.replay_sequences.length !== sequenceCount) {
    throw new Error("sequence_count does not match replay_sequences");
  }
  if (sourceEventCount !== sequenceCount) {
    throw new Error("source_event_count does not match sequence_count");
  }

  const sequences = raw.replay_sequences.map(adaptSequence);
  const seen = new Set<string>();
  for (const sequence of sequences) {
    if (seen.has(sequence.sequence_id)) {
      throw new Error(`duplicate sequence_id: ${sequence.sequence_id}`);
    }
    seen.add(sequence.sequence_id);
  }

  const adaptedFrameCount = sequences.reduce(
    (total, sequence) => total + sequence.frames.length,
    0,
  );
  if (adaptedFrameCount !== totalFrameCount) {
    throw new Error("total_frame_count does not match adapted frames");
  }

  return {
    sourceLabel: "Frozen K26 local JSON",
    basketName,
    sourceEventCount,
    sequenceCount,
    totalFrameCount,
    sequences,
  };
}
