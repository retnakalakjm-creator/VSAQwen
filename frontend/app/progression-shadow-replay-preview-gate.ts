export const PROGRESSION_SHADOW_REPLAY_PREVIEW_GATE = {
  previewEntrypointOnly: true,
  enabledByDefault: false,
  requiresExplicitPreviewEnablement: true,
  offlineSyntheticFixtureOnly: true,
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

export type ProgressionShadowReplayPreviewGateInput = {
  enableOfflinePreview?: boolean;
  allowLiveApiFetch?: boolean;
  allowProductionSignals?: boolean;
  allowQualificationMutation?: boolean;
};

export type ProgressionShadowReplayPreviewGateDecision = {
  enabled: boolean;
  reason:
    | "disabled_by_default"
    | "enabled_for_offline_synthetic_preview"
    | "blocked_for_production_boundary";
  canRenderPreview: boolean;
  production_change_allowed: false;
  live_api_fetch_allowed: false;
  qualification_mutation_allowed: false;
};

const CLOSED_GATE = {
  production_change_allowed: false,
  live_api_fetch_allowed: false,
  qualification_mutation_allowed: false,
} as const;

export function evaluateProgressionShadowReplayPreviewGate(
  input: ProgressionShadowReplayPreviewGateInput = {},
): ProgressionShadowReplayPreviewGateDecision {
  if (
    input.allowLiveApiFetch === true ||
    input.allowProductionSignals === true ||
    input.allowQualificationMutation === true
  ) {
    return {
      ...CLOSED_GATE,
      enabled: false,
      reason: "blocked_for_production_boundary",
      canRenderPreview: false,
    };
  }

  if (input.enableOfflinePreview === true) {
    return {
      ...CLOSED_GATE,
      enabled: true,
      reason: "enabled_for_offline_synthetic_preview",
      canRenderPreview: true,
    };
  }

  return {
    ...CLOSED_GATE,
    enabled: false,
    reason: "disabled_by_default",
    canRenderPreview: false,
  };
}
