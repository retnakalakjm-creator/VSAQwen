"use client";

import { useMemo, useState } from "react";

import type { EffortResultReplaySequence } from "./effort-result-replay-bar";
import { buildEffortResultMarkerOverlays } from "./effort-result-replay-bar";

export const EFFORT_RESULT_REPLAY_EVIDENCE_DRAFT_BOUNDARY = {
  visualReplayEvidenceDraftOnly: true,
  offlinePreviewOnly: true,
  manualReviewOnly: true,
  readsReplaySequencesOnly: true,
  browserMemoryOnly: true,
  exportOnly: true,
  persistenceAllowed: false,
  uploadAllowed: false,
  liveApiFetchAllowed: false,
  routeActivationAllowed: false,
  productionSignalAllowed: false,
  scoringAllowed: false,
  rankingAllowed: false,
  actionabilityAllowed: false,
  detectorActivationAllowed: false,
  scannerStateAllowed: false,
  alertingAllowed: false,
  orderExecutionAllowed: false,
} as const;

export const EFFORT_RESULT_REPLAY_EVIDENCE_DRAFT_FIELDS = [
  "marker_alignment_status",
  "pre_event_context_status",
  "post_event_follow_through_status",
  "counterfactual_scan_status",
  "vsa_smc_quality_status",
  "reviewer_notes",
  "screenshot_filename",
] as const;

export const EFFORT_RESULT_REPLAY_EVIDENCE_STATUS_OPTIONS = [
  "unreviewed",
  "confirmed",
  "needs_attention",
  "rejected",
] as const;

const EFFORT_RESULT_REPLAY_EVIDENCE_STATUS_FIELDS = [
  "marker_alignment_status",
  "pre_event_context_status",
  "post_event_follow_through_status",
  "counterfactual_scan_status",
  "vsa_smc_quality_status",
] as const;

type ReviewStatus = (typeof EFFORT_RESULT_REPLAY_EVIDENCE_STATUS_OPTIONS)[number];
type EvidenceDraftField = (typeof EFFORT_RESULT_REPLAY_EVIDENCE_DRAFT_FIELDS)[number];
type EvidenceStatusField = (typeof EFFORT_RESULT_REPLAY_EVIDENCE_STATUS_FIELDS)[number];

type SequenceEvidenceDraft = {
  sequence_id: string;
  symbol: string;
  target: string;
  event_week_beginning: string;
  marker_labels: string[];
  marker_alignment_status: ReviewStatus;
  pre_event_context_status: ReviewStatus;
  post_event_follow_through_status: ReviewStatus;
  counterfactual_scan_status: ReviewStatus;
  vsa_smc_quality_status: ReviewStatus;
  reviewer_notes: string;
  screenshot_filename: string;
  production_change_allowed: false;
};

type EvidenceDraftState = Record<string, Partial<SequenceEvidenceDraft>>;

type EffortResultReplayEvidenceDraftPanelProps = {
  replaySequences: EffortResultReplaySequence[];
};

const EVIDENCE_FIELD_LABELS: Record<EvidenceStatusField, string> = {
  marker_alignment_status: "Marker alignment",
  pre_event_context_status: "Pre-event context",
  post_event_follow_through_status: "Post-event follow-through",
  counterfactual_scan_status: "Counterfactual scan",
  vsa_smc_quality_status: "VSA/SMC quality",
};

function markerLabelsFor(sequence: EffortResultReplaySequence) {
  const labels = buildEffortResultMarkerOverlays(sequence.frames).map((overlay) => overlay.label);
  return Array.from(new Set(labels));
}

function isReviewStatus(value: unknown): value is ReviewStatus {
  return EFFORT_RESULT_REPLAY_EVIDENCE_STATUS_OPTIONS.includes(value as ReviewStatus);
}

function defaultSequenceEvidenceDraft(sequence: EffortResultReplaySequence): SequenceEvidenceDraft {
  return {
    sequence_id: sequence.sequence_id,
    symbol: sequence.symbol,
    target: sequence.target,
    event_week_beginning: sequence.event_week_beginning,
    marker_labels: markerLabelsFor(sequence),
    marker_alignment_status: "unreviewed",
    pre_event_context_status: "unreviewed",
    post_event_follow_through_status: "unreviewed",
    counterfactual_scan_status: "unreviewed",
    vsa_smc_quality_status: "unreviewed",
    reviewer_notes: "",
    screenshot_filename: "",
    production_change_allowed: false,
  };
}

function mergeSequenceEvidenceDraft(
  sequence: EffortResultReplaySequence,
  draftState: EvidenceDraftState,
): SequenceEvidenceDraft {
  const baseline = defaultSequenceEvidenceDraft(sequence);
  const override = draftState[sequence.sequence_id] ?? {};

  return {
    ...baseline,
    marker_alignment_status: isReviewStatus(override.marker_alignment_status)
      ? override.marker_alignment_status
      : baseline.marker_alignment_status,
    pre_event_context_status: isReviewStatus(override.pre_event_context_status)
      ? override.pre_event_context_status
      : baseline.pre_event_context_status,
    post_event_follow_through_status: isReviewStatus(override.post_event_follow_through_status)
      ? override.post_event_follow_through_status
      : baseline.post_event_follow_through_status,
    counterfactual_scan_status: isReviewStatus(override.counterfactual_scan_status)
      ? override.counterfactual_scan_status
      : baseline.counterfactual_scan_status,
    vsa_smc_quality_status: isReviewStatus(override.vsa_smc_quality_status)
      ? override.vsa_smc_quality_status
      : baseline.vsa_smc_quality_status,
    reviewer_notes: typeof override.reviewer_notes === "string" ? override.reviewer_notes : baseline.reviewer_notes,
    screenshot_filename:
      typeof override.screenshot_filename === "string" ? override.screenshot_filename : baseline.screenshot_filename,
    sequence_id: sequence.sequence_id,
    symbol: sequence.symbol,
    target: sequence.target,
    event_week_beginning: sequence.event_week_beginning,
    marker_labels: markerLabelsFor(sequence),
    production_change_allowed: false,
  };
}

export function buildEffortResultReplayEvidenceExport(
  replaySequences: EffortResultReplaySequence[],
  draftState: EvidenceDraftState,
) {
  const sequenceEvidence = replaySequences.map((sequence) => mergeSequenceEvidenceDraft(sequence, draftState));
  const confirmedSequenceCount = sequenceEvidence.filter((sequence) =>
    EFFORT_RESULT_REPLAY_EVIDENCE_STATUS_FIELDS.every((field) => sequence[field] === "confirmed"),
  ).length;

  return {
    report_type: "effort_result_visual_replay_evidence_draft",
    report_schema_version: 1,
    review_mode: "manual_visual_replay",
    evidence_status:
      sequenceEvidence.length > 0 && confirmedSequenceCount === sequenceEvidence.length
        ? "all_sequences_confirmed"
        : "draft_in_progress",
    sequence_count: sequenceEvidence.length,
    confirmed_sequence_count: confirmedSequenceCount,
    sequence_evidence: sequenceEvidence,
    manual_review_only: true,
    offline_preview_only: true,
    export_only: true,
    persistence_allowed: false,
    upload_allowed: false,
    live_data_allowed: false,
    production_change_allowed: false,
    scoring_allowed: false,
    ranking_allowed: false,
    actionability_allowed: false,
    detector_activation_allowed: false,
    alerting_allowed: false,
    order_execution_allowed: false,
  };
}

export type EffortResultReplayEvidenceExport = ReturnType<typeof buildEffortResultReplayEvidenceExport>;

export function renderEffortResultReplayEvidenceMarkdownDraft(report: EffortResultReplayEvidenceExport) {
  const lines = [
    "# Effort/Result Visual Replay Evidence Draft",
    "",
    "## Summary",
    "",
    `- Review mode: ${report.review_mode}`,
    `- Evidence status: ${report.evidence_status}`,
    `- Sequences: ${report.sequence_count}`,
    `- Confirmed sequences: ${report.confirmed_sequence_count}`,
    "- Manual review only: true",
    "- Offline preview only: true",
    "- Production change allowed: false",
    "",
    "## Sequence Evidence",
    "",
  ];

  for (const sequence of report.sequence_evidence) {
    lines.push(
      `### ${sequence.symbol} ${sequence.event_week_beginning} — ${sequence.target}`,
      "",
      `- Sequence ID: ${sequence.sequence_id}`,
      `- Marker labels: ${sequence.marker_labels.length > 0 ? sequence.marker_labels.join(", ") : "No marker labels"}`,
      `- Marker alignment: ${sequence.marker_alignment_status}`,
      `- Pre-event context: ${sequence.pre_event_context_status}`,
      `- Post-event follow-through: ${sequence.post_event_follow_through_status}`,
      `- Counterfactual scan: ${sequence.counterfactual_scan_status}`,
      `- VSA/SMC quality: ${sequence.vsa_smc_quality_status}`,
      `- Screenshot filename: ${sequence.screenshot_filename || "not provided"}`,
      `- Reviewer notes: ${sequence.reviewer_notes || "not provided"}`,
      "- Production change allowed: false",
      "",
    );
  }

  return lines.join("\n");
}

function updateDraftField(
  current: EvidenceDraftState,
  sequenceId: string,
  field: EvidenceDraftField,
  value: string,
): EvidenceDraftState {
  return {
    ...current,
    [sequenceId]: {
      ...(current[sequenceId] ?? {}),
      [field]: value,
    } as Partial<SequenceEvidenceDraft>,
  };
}

type EvidenceStatusSelectProps = {
  field: EvidenceStatusField;
  label: string;
  sequenceId: string;
  value: ReviewStatus;
  onChange: (field: EvidenceStatusField, value: ReviewStatus) => void;
};

function EvidenceStatusSelect({ field, label, sequenceId, value, onChange }: EvidenceStatusSelectProps) {
  return (
    <label className="evidence-status-field">
      <span>{label}</span>
      <select
        aria-label={`${sequenceId}: ${label}`}
        value={value}
        onChange={(event) => onChange(field, event.target.value as ReviewStatus)}
      >
        {EFFORT_RESULT_REPLAY_EVIDENCE_STATUS_OPTIONS.map((status) => (
          <option key={status} value={status}>
            {status.replace(/_/g, " ")}
          </option>
        ))}
      </select>
    </label>
  );
}

export function EffortResultReplayEvidenceDraftPanel({
  replaySequences,
}: EffortResultReplayEvidenceDraftPanelProps) {
  const [draftState, setDraftState] = useState<EvidenceDraftState>({});

  const evidenceDraft = useMemo(
    () => buildEffortResultReplayEvidenceExport(replaySequences, draftState),
    [replaySequences, draftState],
  );
  const jsonDraft = useMemo(() => JSON.stringify(evidenceDraft, null, 2), [evidenceDraft]);
  const markdownDraft = useMemo(() => renderEffortResultReplayEvidenceMarkdownDraft(evidenceDraft), [evidenceDraft]);

  const updateSequenceDraft = (sequenceId: string, field: EvidenceDraftField, value: string) => {
    setDraftState((current) => updateDraftField(current, sequenceId, field, value));
  };

  return (
    <aside
      className="panel effort-result-replay-evidence-draft-panel"
      aria-label="Effort Result visual replay evidence draft panel"
      data-visual-evidence-draft-panel="true"
      data-manual-review-only="true"
      data-offline-preview-only="true"
      data-export-only="true"
      data-persistence-allowed="false"
      data-production-change-allowed="false"
    >
      <div className="workspace-heading">
        <div>
          <span className="section-kicker">VISUAL REPLAY EVIDENCE</span>
          <h2>Manual evidence draft</h2>
        </div>
        <span>{evidenceDraft.sequence_count} sequences</span>
      </div>

      <p>
        Capture what the reviewer sees as copy-ready evidence only. Entries stay in temporary browser component state
        and are not saved, uploaded, scored, ranked, alerted, or used for order execution.
      </p>

      <dl className="replay-evidence-boundary">
        <div>
          <dt>Evidence mode</dt>
          <dd>{EFFORT_RESULT_REPLAY_EVIDENCE_DRAFT_BOUNDARY.exportOnly ? "copy-ready draft" : "disabled"}</dd>
        </div>
        <div>
          <dt>Saved review state</dt>
          <dd>{EFFORT_RESULT_REPLAY_EVIDENCE_DRAFT_BOUNDARY.persistenceAllowed ? "allowed" : "disabled"}</dd>
        </div>
        <div>
          <dt>Upload behavior</dt>
          <dd>{EFFORT_RESULT_REPLAY_EVIDENCE_DRAFT_BOUNDARY.uploadAllowed ? "allowed" : "disabled"}</dd>
        </div>
      </dl>

      <div className="replay-evidence-sequence-list">
        {evidenceDraft.sequence_evidence.map((sequenceDraft) => {
          const safeSequenceId = sequenceDraft.sequence_id.replace(/[^a-zA-Z0-9_-]/g, "-");

          return (
            <section
              key={sequenceDraft.sequence_id}
              className="replay-evidence-sequence-card"
              aria-label={`Evidence draft ${sequenceDraft.symbol} ${sequenceDraft.event_week_beginning}`}
              data-evidence-sequence-id={sequenceDraft.sequence_id}
              data-symbol={sequenceDraft.symbol}
              data-target={sequenceDraft.target}
              data-production-change-allowed="false"
            >
              <div className="workspace-heading">
                <div>
                  <span className="section-kicker">{sequenceDraft.symbol}</span>
                  <h3>{sequenceDraft.target}</h3>
                </div>
                <span>{sequenceDraft.event_week_beginning}</span>
              </div>

              <p>Marker labels: {sequenceDraft.marker_labels.join(", ") || "No marker labels"}</p>

              <div className="replay-evidence-status-grid">
                {EFFORT_RESULT_REPLAY_EVIDENCE_STATUS_FIELDS.map((field) => (
                  <EvidenceStatusSelect
                    key={field}
                    field={field}
                    label={EVIDENCE_FIELD_LABELS[field]}
                    sequenceId={sequenceDraft.sequence_id}
                    value={sequenceDraft[field]}
                    onChange={(statusField, value) => updateSequenceDraft(sequenceDraft.sequence_id, statusField, value)}
                  />
                ))}
              </div>

              <label className="evidence-text-field" htmlFor={`${safeSequenceId}-reviewer-notes`}>
                <span>Reviewer notes</span>
                <textarea
                  id={`${safeSequenceId}-reviewer-notes`}
                  aria-label={`${sequenceDraft.sequence_id}: reviewer notes`}
                  placeholder="Write what you observed in the replay: bar location, context, follow-through, and SMC/VSA quality."
                  value={sequenceDraft.reviewer_notes}
                  onChange={(event) => updateSequenceDraft(sequenceDraft.sequence_id, "reviewer_notes", event.target.value)}
                />
              </label>

              <label className="evidence-text-field" htmlFor={`${safeSequenceId}-screenshot-filename`}>
                <span>Screenshot filename</span>
                <input
                  id={`${safeSequenceId}-screenshot-filename`}
                  aria-label={`${sequenceDraft.sequence_id}: screenshot filename`}
                  placeholder={`${safeSequenceId}.png`}
                  type="text"
                  value={sequenceDraft.screenshot_filename}
                  onChange={(event) =>
                    updateSequenceDraft(sequenceDraft.sequence_id, "screenshot_filename", event.target.value)
                  }
                />
              </label>
            </section>
          );
        })}
      </div>

      <section className="replay-evidence-export-card" aria-label="Copy-ready visual replay evidence draft">
        <h3>Copy-ready JSON draft</h3>
        <textarea
          readOnly
          aria-label="Copy-ready visual replay evidence JSON draft"
          rows={14}
          value={jsonDraft}
        />
      </section>

      <section className="replay-evidence-export-card" aria-label="Copy-ready visual replay evidence markdown draft">
        <h3>Copy-ready Markdown draft</h3>
        <textarea
          readOnly
          aria-label="Copy-ready visual replay evidence Markdown draft"
          rows={14}
          value={markdownDraft}
        />
      </section>
    </aside>
  );
}
