export const EFFORT_RESULT_REPLAY_PREVIEW_ROUTE_BOUNDARY = {
  route: "/replay/effort-result",
  routePurpose: "dev_only_offline_visual_review",
  devOnlyOfflinePreview: true,
  enabledInProductionByDefault: false,
  usesOfflineFixtureOnly: true,
  usesExistingPreviewGate: true,
  liveApiFetchAllowed: false,
  productionSignalAllowed: false,
  scoringAllowed: false,
  rankingAllowed: false,
  actionabilityAllowed: false,
  detectorActivationAllowed: false,
  scannerStateAllowed: false,
  persistenceAllowed: false,
  orderExecutionAllowed: false,
} as const;

export function isEffortResultReplayPreviewRouteEnabled(
  environment = process.env.NODE_ENV,
): boolean {
  return environment !== "production";
}
