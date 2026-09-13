export const EFFORT_RESULT_REPLAY_PREVIEW_GATE = {
  previewEntrypointOnly: true,
  enabledByDefault: false,
  requiresExplicitPreviewEnablement: true,
  offlineDemoHarnessOnly: true,
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

export type EffortResultReplayPreviewGateReason =
  | "disabled_by_default"
  | "enabled_for_offline_demo_only"
  | "blocked_for_production_boundary";

export type EffortResultReplayPreviewGateInput = {
  enableOfflinePreview?: boolean;
  allowRouteActivation?: boolean;
  allowLiveApiFetch?: boolean;
  allowProductionSignals?: boolean;
};

export type EffortResultReplayPreviewGateDecision = {
  enabled: boolean;
  reason: EffortResultReplayPreviewGateReason;
  source: "default" | "explicit-prop";
  canRenderDemoHarness: boolean;
  production_change_allowed: false;
  route_activation_allowed: false;
  live_api_fetch_allowed: false;
};

const CLOSED_GATE_DECISION = {
  production_change_allowed: false,
  route_activation_allowed: false,
  live_api_fetch_allowed: false,
} as const;

export function evaluateEffortResultReplayPreviewGate(
  input: EffortResultReplayPreviewGateInput = {},
): EffortResultReplayPreviewGateDecision {
  const blockedByProductionBoundary =
    input.allowRouteActivation === true ||
    input.allowLiveApiFetch === true ||
    input.allowProductionSignals === true;

  if (blockedByProductionBoundary) {
    return {
      ...CLOSED_GATE_DECISION,
      enabled: false,
      reason: "blocked_for_production_boundary",
      source: "explicit-prop",
      canRenderDemoHarness: false,
    };
  }

  if (input.enableOfflinePreview === true) {
    return {
      ...CLOSED_GATE_DECISION,
      enabled: true,
      reason: "enabled_for_offline_demo_only",
      source: "explicit-prop",
      canRenderDemoHarness: true,
    };
  }

  return {
    ...CLOSED_GATE_DECISION,
    enabled: false,
    reason: "disabled_by_default",
    source: "default",
    canRenderDemoHarness: false,
  };
}
