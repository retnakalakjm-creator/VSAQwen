import type { Metadata } from "next";

import { EffortResultReplayPreviewEntrypoint } from "../../effort-result-replay-preview-entrypoint";
import { EFFORT_RESULT_REPLAY_PREVIEW_GATE } from "../../effort-result-replay-preview-gate";
import {
  EFFORT_RESULT_REPLAY_PREVIEW_ROUTE_BOUNDARY,
  isEffortResultReplayPreviewRouteEnabled,
} from "./preview-route-boundary";

export const metadata: Metadata = {
  title: "Effort/Result Replay Preview",
  description: "Dev-only offline Effort/Result replay preview using committed fixture data.",
  robots: {
    index: false,
    follow: false,
  },
};

export const dynamic = "force-static";
export const revalidate = false;

export default function EffortResultReplayPreviewRoute() {
  const enableOfflinePreview = isEffortResultReplayPreviewRouteEnabled();

  return (
    <main
      className="workspace-shell effort-result-replay-preview-route"
      data-route={EFFORT_RESULT_REPLAY_PREVIEW_ROUTE_BOUNDARY.route}
      data-route-purpose={EFFORT_RESULT_REPLAY_PREVIEW_ROUTE_BOUNDARY.routePurpose}
      data-dev-only-offline-preview="true"
      data-offline-preview-enabled={enableOfflinePreview ? "true" : "false"}
      data-live-api-fetch-allowed="false"
      data-production-change-allowed="false"
    >
      <section className="panel replay-preview-route-boundary" aria-label="Replay preview route boundary">
        <span className="section-kicker">DEV-ONLY OFFLINE REPLAY</span>
        <h1>Effort/Result replay preview</h1>
        <p>
          This page is a local visual review entrypoint for committed fixture data only. Production runtime keeps
          the preview gate closed by default and this page does not fetch live data, change signals, or execute orders.
        </p>
        <dl>
          <div>
            <dt>Preview route</dt>
            <dd>{EFFORT_RESULT_REPLAY_PREVIEW_ROUTE_BOUNDARY.route}</dd>
          </div>
          <div>
            <dt>Preview enabled in production by default</dt>
            <dd>{EFFORT_RESULT_REPLAY_PREVIEW_ROUTE_BOUNDARY.enabledInProductionByDefault ? "yes" : "no"}</dd>
          </div>
          <div>
            <dt>Existing preview gate default</dt>
            <dd>{EFFORT_RESULT_REPLAY_PREVIEW_GATE.enabledByDefault ? "enabled" : "disabled"}</dd>
          </div>
        </dl>
      </section>

      <EffortResultReplayPreviewEntrypoint enableOfflinePreview={enableOfflinePreview} />
    </main>
  );
}
