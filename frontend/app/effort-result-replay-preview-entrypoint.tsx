"use client";

import { EffortResultReplayDemoHarness } from "./effort-result-replay-demo-harness";
import {
  EFFORT_RESULT_REPLAY_PREVIEW_GATE,
  evaluateEffortResultReplayPreviewGate,
} from "./effort-result-replay-preview-gate";

type EffortResultReplayPreviewEntrypointProps = {
  enableOfflinePreview?: boolean;
};

export function EffortResultReplayPreviewEntrypoint({
  enableOfflinePreview = false,
}: EffortResultReplayPreviewEntrypointProps) {
  const gateDecision = evaluateEffortResultReplayPreviewGate({ enableOfflinePreview });

  if (!gateDecision.enabled) {
    return (
      <section
        className="panel effort-result-replay-preview-entrypoint"
        aria-label="Effort Result replay preview entrypoint"
        data-preview-gate="disabled"
        data-demo-only="true"
        data-production-change-allowed="false"
      >
        <span className="section-kicker">OFFLINE SHADOW REPLAY PREVIEW</span>
        <h2>Replay preview is gated off</h2>
        <p>
          This entrypoint is disabled by default. It does not fetch live data, expose a route,
          activate scoring, rank symbols, trigger alerts, persist scanner state, or submit orders.
        </p>
        <dl>
          <div>
            <dt>Gate reason</dt>
            <dd>{gateDecision.reason}</dd>
          </div>
          <div>
            <dt>Preview enabled by default</dt>
            <dd>{EFFORT_RESULT_REPLAY_PREVIEW_GATE.enabledByDefault ? "yes" : "no"}</dd>
          </div>
          <div>
            <dt>Route activation</dt>
            <dd>{EFFORT_RESULT_REPLAY_PREVIEW_GATE.routeActivationAllowed ? "allowed" : "disabled"}</dd>
          </div>
        </dl>
      </section>
    );
  }

  return (
    <section
      className="panel effort-result-replay-preview-entrypoint"
      aria-label="Effort Result replay preview entrypoint"
      data-preview-gate="enabled"
      data-demo-only="true"
      data-production-change-allowed="false"
    >
      <div className="replay-contract-note" data-live-api-fetch-allowed="false">
        Explicit offline preview only. The demo harness renders committed fixture data and remains unrouted.
      </div>
      <EffortResultReplayDemoHarness />
    </section>
  );
}

export function DisabledEffortResultReplayPreviewEntrypoint() {
  return <EffortResultReplayPreviewEntrypoint />;
}
