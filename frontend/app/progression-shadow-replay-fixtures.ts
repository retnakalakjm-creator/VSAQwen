export type ProgressionShadowSemanticRole =
  | "TRANSITION_WARNING"
  | "ALIGNED_PROGRESSION_OBSERVATION"
  | "NEUTRAL_PROGRESSION_OBSERVATION"
  | "UNKNOWN_TREND_CONTEXT_OBSERVATION";

export type ProgressionShadowReplayFrame = {
  bar_index: number;
  week: string;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
  is_event_bar: boolean;
  event_direction: "bullish" | "bearish" | null;
  trend_alignment: "opposed" | "aligned" | "neutral" | "unknown" | null;
  semantic_role: ProgressionShadowSemanticRole | null;
  projected_transition_direction: "bullish" | "bearish" | null;
  reversal_confirmed: false;
  persistent_direction_claim: false;
  affects_qualification: false;
  affects_scoring: false;
  is_actionable: false;
};

export type ProgressionShadowReplaySequence = {
  sequence_id: string;
  title: string;
  description: string;
  event_bar_index: number;
  source?: "synthetic-k25-fixture" | "k26-offline-dataset";
  symbol?: string;
  event_week?: string;
  source_event_bar_index?: number;
  resolved_event_bar_index?: number;
  event_direction?: "bullish" | "bearish";
  trend_alignment?: "opposed" | "aligned" | "neutral" | "unknown";
  semantic_role?: ProgressionShadowSemanticRole;
  projected_transition_direction?: "bullish" | "bearish" | null;
  frames: ProgressionShadowReplayFrame[];
};

export const PROGRESSION_SHADOW_REPLAY_FIXTURE_BOUNDARY = {
  source: "synthetic-k25-progression-shadow-replay-fixture",
  syntheticFixtureOnly: true,
  auditOnly: true,
  shadowOnly: true,
  liveApiFetchAllowed: false,
  productionSignalAllowed: false,
  scoringAllowed: false,
  rankingAllowed: false,
  actionabilityAllowed: false,
  qualificationMutationAllowed: false,
  scannerStateAllowed: false,
  persistenceAllowed: false,
  alertingAllowed: false,
  orderExecutionAllowed: false,
} as const;

const safeFrame = (
  frame: Omit<
    ProgressionShadowReplayFrame,
    | "reversal_confirmed"
    | "persistent_direction_claim"
    | "affects_qualification"
    | "affects_scoring"
    | "is_actionable"
  >,
): ProgressionShadowReplayFrame => ({
  ...frame,
  reversal_confirmed: false,
  persistent_direction_claim: false,
  affects_qualification: false,
  affects_scoring: false,
  is_actionable: false,
});

export const progressionShadowReplaySequences:
  ProgressionShadowReplaySequence[] = [
  {
    sequence_id: "bullish-opposed-transition-warning",
    title: "Bullish progression opposed to downtrend",
    description:
      "The event projects only a bullish transition warning. " +
      "It does not confirm a reversal or persist a new direction.",
    event_bar_index: 2,
    frames: [
      safeFrame({
        bar_index: 0,
        week: "2026-01-05",
        open: 104,
        high: 106,
        low: 99,
        close: 101,
        volume: 1000,
        is_event_bar: false,
        event_direction: null,
        trend_alignment: null,
        semantic_role: null,
        projected_transition_direction: null,
      }),
      safeFrame({
        bar_index: 1,
        week: "2026-01-12",
        open: 101,
        high: 102,
        low: 96,
        close: 98,
        volume: 1120,
        is_event_bar: false,
        event_direction: null,
        trend_alignment: null,
        semantic_role: null,
        projected_transition_direction: null,
      }),
      safeFrame({
        bar_index: 2,
        week: "2026-01-19",
        open: 98,
        high: 104,
        low: 97,
        close: 103,
        volume: 1390,
        is_event_bar: true,
        event_direction: "bullish",
        trend_alignment: "opposed",
        semantic_role: "TRANSITION_WARNING",
        projected_transition_direction: "bullish",
      }),
      safeFrame({
        bar_index: 3,
        week: "2026-01-26",
        open: 103,
        high: 106,
        low: 101,
        close: 105,
        volume: 1210,
        is_event_bar: false,
        event_direction: null,
        trend_alignment: null,
        semantic_role: null,
        projected_transition_direction: null,
      }),
      safeFrame({
        bar_index: 4,
        week: "2026-02-02",
        open: 105,
        high: 106,
        low: 100,
        close: 101,
        volume: 1180,
        is_event_bar: false,
        event_direction: null,
        trend_alignment: null,
        semantic_role: null,
        projected_transition_direction: null,
      }),
    ],
  },
  {
    sequence_id: "bearish-aligned-observation",
    title: "Bearish progression aligned with downtrend",
    description:
      "Aligned progression remains a descriptive observation; " +
      "K24 does not promote it to continuation confirmation.",
    event_bar_index: 2,
    frames: [
      safeFrame({
        bar_index: 0,
        week: "2026-02-09",
        open: 210,
        high: 214,
        low: 207,
        close: 211,
        volume: 900,
        is_event_bar: false,
        event_direction: null,
        trend_alignment: null,
        semantic_role: null,
        projected_transition_direction: null,
      }),
      safeFrame({
        bar_index: 1,
        week: "2026-02-16",
        open: 211,
        high: 212,
        low: 204,
        close: 205,
        volume: 980,
        is_event_bar: false,
        event_direction: null,
        trend_alignment: null,
        semantic_role: null,
        projected_transition_direction: null,
      }),
      safeFrame({
        bar_index: 2,
        week: "2026-02-23",
        open: 205,
        high: 207,
        low: 199,
        close: 201,
        volume: 1320,
        is_event_bar: true,
        event_direction: "bearish",
        trend_alignment: "aligned",
        semantic_role: "ALIGNED_PROGRESSION_OBSERVATION",
        projected_transition_direction: null,
      }),
      safeFrame({
        bar_index: 3,
        week: "2026-03-02",
        open: 201,
        high: 205,
        low: 198,
        close: 204,
        volume: 1010,
        is_event_bar: false,
        event_direction: null,
        trend_alignment: null,
        semantic_role: null,
        projected_transition_direction: null,
      }),
      safeFrame({
        bar_index: 4,
        week: "2026-03-09",
        open: 204,
        high: 209,
        low: 203,
        close: 208,
        volume: 960,
        is_event_bar: false,
        event_direction: null,
        trend_alignment: null,
        semantic_role: null,
        projected_transition_direction: null,
      }),
    ],
  },
  {
    sequence_id: "neutral-progression-observation",
    title: "Progression while trend context is neutral",
    description:
      "Neutral context remains descriptive and carries no projected transition direction.",
    event_bar_index: 2,
    frames: [
      safeFrame({
        bar_index: 0,
        week: "2026-03-16",
        open: 150,
        high: 154,
        low: 148,
        close: 152,
        volume: 760,
        is_event_bar: false,
        event_direction: null,
        trend_alignment: null,
        semantic_role: null,
        projected_transition_direction: null,
      }),
      safeFrame({
        bar_index: 1,
        week: "2026-03-23",
        open: 152,
        high: 155,
        low: 150,
        close: 151,
        volume: 800,
        is_event_bar: false,
        event_direction: null,
        trend_alignment: null,
        semantic_role: null,
        projected_transition_direction: null,
      }),
      safeFrame({
        bar_index: 2,
        week: "2026-03-30",
        open: 151,
        high: 156,
        low: 149,
        close: 154,
        volume: 920,
        is_event_bar: true,
        event_direction: "bullish",
        trend_alignment: "neutral",
        semantic_role: "NEUTRAL_PROGRESSION_OBSERVATION",
        projected_transition_direction: null,
      }),
      safeFrame({
        bar_index: 3,
        week: "2026-04-06",
        open: 154,
        high: 157,
        low: 151,
        close: 153,
        volume: 810,
        is_event_bar: false,
        event_direction: null,
        trend_alignment: null,
        semantic_role: null,
        projected_transition_direction: null,
      }),
      safeFrame({
        bar_index: 4,
        week: "2026-04-13",
        open: 153,
        high: 155,
        low: 149,
        close: 150,
        volume: 840,
        is_event_bar: false,
        event_direction: null,
        trend_alignment: null,
        semantic_role: null,
        projected_transition_direction: null,
      }),
    ],
  },
];
