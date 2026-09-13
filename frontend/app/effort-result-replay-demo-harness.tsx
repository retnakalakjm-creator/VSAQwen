"use client";

import type { EffortResultReplaySequence } from "./effort-result-replay-bar";
import { EffortResultReplayBar } from "./effort-result-replay-bar";
import {
  EFFORT_RESULT_REPLAY_DATASET_FIXTURE_PRODUCTION_BOUNDARY,
  EFFORT_RESULT_REPLAY_DATASET_FIXTURE_SOURCE,
  offlineEffortResultDatasetReplaySequences,
} from "./effort-result-replay-dataset-fixture";
import { EffortResultReplayEvidenceDraftPanel } from "./effort-result-replay-evidence-draft-panel";
import { EffortResultReplayReviewChecklist } from "./effort-result-replay-review-checklist";
import {
  EFFORT_RESULT_REPLAY_FIXTURE_PRODUCTION_BOUNDARY,
  EFFORT_RESULT_REPLAY_FIXTURE_SOURCE,
  offlineEffortResultReplaySequences,
} from "./effort-result-replay-fixtures";

export const offlineEffortResultReplayPreviewSequences: EffortResultReplaySequence[] = [
  ...offlineEffortResultReplaySequences,
  ...offlineEffortResultDatasetReplaySequences,
];

export function getOfflineEffortResultReplayPreviewSequences() {
  return offlineEffortResultReplayPreviewSequences;
}

export function EffortResultReplayDemoHarness() {
  const replaySequences = getOfflineEffortResultReplayPreviewSequences();

  return (
    <section
      className="panel effort-result-replay-demo-harness"
      aria-label="Offline Effort Result replay demo harness"
      data-demo-only="true"
      data-production-change-allowed="false"
      data-dataset-backed-preview="true"
      data-visual-review-checklist="true"
      data-visual-evidence-draft-panel="true"
    >
      <div className="workspace-heading">
        <div>
          <span className="section-kicker">OFFLINE SHADOW REPLAY DEMO</span>
          <h2>Effort/Result replay fixture harness</h2>
        </div>
        <span>
          {offlineEffortResultReplaySequences.length} static + {offlineEffortResultDatasetReplaySequences.length} dataset
          fixtures
        </span>
      </div>

      <p>
        Static visual validation harness only. It renders committed fixture data plus an adapted dataset-shaped
        sample and does not fetch live data, activate scoring, rank symbols, trigger alerts, persist scanner state,
        or submit orders.
      </p>

      <dl className="replay-demo-boundary">
        <div>
          <dt>Fixture source</dt>
          <dd>{EFFORT_RESULT_REPLAY_FIXTURE_SOURCE}</dd>
        </div>
        <div>
          <dt>Dataset fixture source</dt>
          <dd>{EFFORT_RESULT_REPLAY_DATASET_FIXTURE_SOURCE}</dd>
        </div>
        <div>
          <dt>Dataset adapter</dt>
          <dd>{EFFORT_RESULT_REPLAY_DATASET_FIXTURE_PRODUCTION_BOUNDARY.usesDatasetAdapter ? "read-only" : "disabled"}</dd>
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

      <div
        className="replay-preview-workbench"
        data-visual-review-workbench="true"
        data-visual-evidence-draft-panel="true"
      >
        <EffortResultReplayBar replaySequences={replaySequences} />
        <EffortResultReplayReviewChecklist replaySequences={replaySequences} />
        <EffortResultReplayEvidenceDraftPanel replaySequences={replaySequences} />
      </div>
    </section>
  );
}
