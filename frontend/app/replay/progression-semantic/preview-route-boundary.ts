export const PROGRESSION_SHADOW_REPLAY_ROUTE_BOUNDARY = {
  route: "/replay/progression-semantic",
  routePurpose: "dev_only_offline_shadow_semantic_review",
  devOnlyOfflinePreview: true,
  enabledInProductionByDefault: false,
  usesSyntheticFixtureOnly: true,
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

export function isProgressionShadowReplayRouteEnabled(
  environment = process.env.NODE_ENV,
): boolean {
  return environment !== "production";
}
