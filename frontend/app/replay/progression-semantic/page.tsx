import type { Metadata } from "next";

import {
  ProgressionShadowReplayPreviewEntrypoint,
} from "../../progression-shadow-replay-preview-entrypoint";
import {
  PROGRESSION_SHADOW_REPLAY_PREVIEW_GATE,
} from "../../progression-shadow-replay-preview-gate";
import {
  PROGRESSION_SHADOW_REPLAY_ROUTE_BOUNDARY,
  isProgressionShadowReplayRouteEnabled,
} from "./preview-route-boundary";

export const metadata: Metadata = {
  title: "Progression Shadow Semantic Replay",
  description:
    "Dev-only offline replay preview for shadow progression semantic roles.",
  robots: {
    index: false,
    follow: false,
  },
};

export const dynamic = "force-static";
export const revalidate = false;

export default function ProgressionShadowReplayRoute() {
  const enableOfflinePreview = isProgressionShadowReplayRouteEnabled();

  return (
    <main
      className="workspace-shell progression-shadow-replay-route"
      data-route={PROGRESSION_SHADOW_REPLAY_ROUTE_BOUNDARY.route}
      data-route-purpose={PROGRESSION_SHADOW_REPLAY_ROUTE_BOUNDARY.routePurpose}
      data-dev-only-offline-preview="true"
      data-offline-preview-enabled={enableOfflinePreview ? "true" : "false"}
      data-live-api-fetch-allowed="false"
      data-production-change-allowed="false"
    >
      <section className="panel replay-preview-route-boundary">
        <span className="section-kicker">DEV-ONLY OFFLINE REPLAY</span>
        <h1>Progression shadow semantic replay</h1>
        <p>
          This route visualizes synthetic K24-style shadow semantic markers.
          It never fetches live API data and cannot modify qualification,
          scoring, actionability, persistence, alerts, or orders.
        </p>
        <dl>
          <div>
            <dt>Route</dt>
            <dd>{PROGRESSION_SHADOW_REPLAY_ROUTE_BOUNDARY.route}</dd>
          </div>
          <div>
            <dt>Enabled in production by default</dt>
            <dd>
              {PROGRESSION_SHADOW_REPLAY_ROUTE_BOUNDARY.enabledInProductionByDefault
                ? "yes"
                : "no"}
            </dd>
          </div>
          <div>
            <dt>Preview gate default</dt>
            <dd>
              {PROGRESSION_SHADOW_REPLAY_PREVIEW_GATE.enabledByDefault
                ? "enabled"
                : "disabled"}
            </dd>
          </div>
        </dl>
      </section>

      <ProgressionShadowReplayPreviewEntrypoint
        enableOfflinePreview={enableOfflinePreview}
      />
    </main>
  );
}
