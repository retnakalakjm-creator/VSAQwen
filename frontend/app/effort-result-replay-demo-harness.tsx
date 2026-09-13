"use client";

import { EffortResultReplayBar } from "./effort-result-replay-bar";
import {
  EFFORT_RESULT_REPLAY_FIXTURE_PRODUCTION_BOUNDARY,
  EFFORT_RESULT_REPLAY_FIXTURE_SOURCE,
  offlineEffortResultReplaySequences,
} from "./effort-result-replay-fixtures";

export function EffortResultReplayDemoHarness() {
  return (
    <section
      className="panel effort-result-replay-demo-harness"
      aria-label="Offline Effort Result replay demo harness"
      data-demo-only="true"
      data-production-change-allowed="false"
    >
      <div className="workspace-heading">
        <div>
          <span className="section-kicker">OFFLINE SHADOW REPLAY DEMO</span>
          <h2>Effort/Result replay fixture harness</h2>
        </div>
        <span>{offlineEffortResultReplaySequences.length} fixtures</span>
      </div>

      <p>
        Static visual validation harness only. It renders committed fixture data and does not fetch live data,
        expose a route, activate scoring, rank symbols, trigger alerts, persist scanner state, or submit orders.
      </p>

      <dl className="replay-demo-boundary">
        <div>
          <dt>Fixture source</dt>
          <dd>{EFFORT_RESULT_REPLAY_FIXTURE_SOURCE}</dd>
        </div>
        <div>
          <dt>Live data fetch</dt>
          <dd>{EFFORT_RESULT_REPLAY_FIXTURE_PRODUCTION_BOUNDARY.liveApiFetchAllowed ? "allowed" : "disabled"}</dd>
        </div>
        <div>
          <dt>Production signals</dt>
          <dd>{EFFORT_RESULT_REPLAY_FIXTURE_PRODUCTION_BOUNDARY.productionSignalAllowed ? "allowed" : "disabled"}</dd>
        </div>
      </dl>

      <EffortResultReplayBar replaySequences={offlineEffortResultReplaySequences} />
    </section>
  );
}
