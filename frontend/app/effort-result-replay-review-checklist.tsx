"use client";

import type { EffortResultReplaySequence } from "./effort-result-replay-bar";
import { buildEffortResultMarkerOverlays } from "./effort-result-replay-bar";

export const EFFORT_RESULT_REPLAY_REVIEW_CHECKLIST_BOUNDARY = {
  visualReviewChecklistOnly: true,
  offlinePreviewOnly: true,
  readsReplaySequencesOnly: true,
  manualReviewOnly: true,
  liveApiFetchAllowed: false,
  routeActivationAllowed: false,
  productionSignalAllowed: false,
  scoringAllowed: false,
  rankingAllowed: false,
  actionabilityAllowed: false,
  detectorActivationAllowed: false,
  scannerStateAllowed: false,
  persistenceAllowed: false,
  alertingAllowed: false,
  orderExecutionAllowed: false,
} as const;

export const EFFORT_RESULT_REPLAY_REVIEW_CHECKLIST_QUESTIONS = [
  "Did the marker appear on the correct bar?",
  "Did the prior context support the signal?",
  "Did follow-through confirm or reject it?",
  "Did the setup look like real VSA/SMC quality?",
] as const;

type EffortResultReplayReviewChecklistProps = {
  replaySequences: EffortResultReplaySequence[];
};

type ReplayFrame = EffortResultReplaySequence["frames"][number];

function sequenceEventFrame(sequence: EffortResultReplaySequence): ReplayFrame | undefined {
  return (
    sequence.frames.find((frame) => frame.is_event_bar) ??
    sequence.frames.find((frame) => frame.bar_index === sequence.event_bar_index) ??
    sequence.frames[0]
  );
}

function frameSummary(frame: ReplayFrame | undefined) {
  if (!frame) return "No frame available";
  return `${frame.week_beginning} close ${frame.close} volume ${frame.volume_ratio ?? "—"} spread ${
    frame.spread_ratio ?? "—"
  }`;
}

function expectedRelationshipFor(sequence: EffortResultReplaySequence) {
  const eventFrame = sequenceEventFrame(sequence);
  return eventFrame?.relationship ?? eventFrame?.effort_result_candidate ?? sequence.target;
}

function priorContextFor(sequence: EffortResultReplaySequence) {
  const priorFrame = [...sequence.frames].reverse().find((frame) => frame.replay_offset < 0);
  return frameSummary(priorFrame);
}

function followThroughFor(sequence: EffortResultReplaySequence) {
  const forwardFrame = sequence.frames.find((frame) => frame.replay_offset > 0);
  return frameSummary(forwardFrame);
}

function markerLabelsFor(sequence: EffortResultReplaySequence) {
  const labels = buildEffortResultMarkerOverlays(sequence.frames).map((overlay) => overlay.label);
  const uniqueLabels = Array.from(new Set(labels));
  return uniqueLabels.length > 0 ? uniqueLabels.join(", ") : "No shadow marker";
}

export function EffortResultReplayReviewChecklist({
  replaySequences,
}: EffortResultReplayReviewChecklistProps) {
  return (
    <aside
      className="panel effort-result-replay-review-checklist"
      aria-label="Effort Result visual replay review checklist"
      data-visual-review-checklist="true"
      data-manual-review-only="true"
      data-offline-preview-only="true"
      data-production-change-allowed="false"
    >
      <div className="workspace-heading">
        <div>
          <span className="section-kicker">VISUAL REPLAY REVIEW</span>
          <h2>Manual Effort/Result checklist</h2>
        </div>
        <span>{replaySequences.length} sequences</span>
      </div>

      <p>
        Review each replay sequence visually before any production discussion. This checklist reads already-provided
        replay frames only and does not fetch live data, persist review state, score, rank, alert, or submit orders.
      </p>

      <dl className="replay-review-boundary">
        <div>
          <dt>Review mode</dt>
          <dd>{EFFORT_RESULT_REPLAY_REVIEW_CHECKLIST_BOUNDARY.manualReviewOnly ? "manual only" : "disabled"}</dd>
        </div>
        <div>
          <dt>Replay input</dt>
          <dd>{EFFORT_RESULT_REPLAY_REVIEW_CHECKLIST_BOUNDARY.readsReplaySequencesOnly ? "provided sequences" : "disabled"}</dd>
        </div>
        <div>
          <dt>Persistence</dt>
          <dd>{EFFORT_RESULT_REPLAY_REVIEW_CHECKLIST_BOUNDARY.persistenceAllowed ? "allowed" : "disabled"}</dd>
        </div>
      </dl>

      <div className="replay-review-sequence-list">
        {replaySequences.map((sequence) => {
          const safeSequenceId = sequence.sequence_id.replace(/[^a-zA-Z0-9_-]/g, "-");

          return (
            <section
              key={sequence.sequence_id}
              className="replay-review-sequence-card"
              aria-label={`Review ${sequence.symbol} ${sequence.event_week_beginning}`}
              data-review-sequence-id={sequence.sequence_id}
              data-target={sequence.target}
              data-symbol={sequence.symbol}
              data-event-week={sequence.event_week_beginning}
              data-production-change-allowed="false"
            >
              <div className="workspace-heading">
                <div>
                  <span className="section-kicker">{sequence.symbol}</span>
                  <h3>{sequence.target}</h3>
                </div>
                <span>{sequence.event_week_beginning}</span>
              </div>

              <dl className="replay-review-sequence-facts">
                <div>
                  <dt>Expected relationship</dt>
                  <dd>{expectedRelationshipFor(sequence)}</dd>
                </div>
                <div>
                  <dt>Marker labels</dt>
                  <dd>{markerLabelsFor(sequence)}</dd>
                </div>
                <div>
                  <dt>Prior context</dt>
                  <dd>{priorContextFor(sequence)}</dd>
                </div>
                <div>
                  <dt>Follow-through</dt>
                  <dd>{followThroughFor(sequence)}</dd>
                </div>
              </dl>

              <ul className="replay-review-questions">
                {EFFORT_RESULT_REPLAY_REVIEW_CHECKLIST_QUESTIONS.map((question, questionIndex) => {
                  const questionId = `${safeSequenceId}-review-question-${questionIndex}`;

                  return (
                    <li key={question}>
                      <input id={questionId} type="checkbox" aria-label={`${sequence.sequence_id}: ${question}`} />
                      <label htmlFor={questionId}>{question}</label>
                    </li>
                  );
                })}
              </ul>
            </section>
          );
        })}
      </div>
    </aside>
  );
}
