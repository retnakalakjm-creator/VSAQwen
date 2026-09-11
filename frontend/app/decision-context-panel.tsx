"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import {
  buildPlainEnglishLegendLookup,
  plainEnglishLegendText,
  type LegendRegistryPayload,
} from "./plain-english-legend-client";

type DecisionContextEvent = {
  bar_index: number;
  week: string;
  code: string;
  category: string;
  direction: string;
  strength: number;
  quality: number;
  observation: string;
  description: string;
  role: string;
};

type StructuralSwingMemory = {
  pivot_bar_index: number;
  confirmation_bar_index: number;
  pivot_week: string;
  type: string;
  label: string | null;
  price: number;
  grade: string;
  is_failed: boolean;
  score: number | null;
};

type VSAStorySummary = {
  headline: string;
  summary: string;
  confirmation_condition: string;
  invalidation_condition: string;
  what_to_expect_next: string[];
};

type QualificationLifecycle = {
  qualification: string;
  qualification_side: string;
  status: string;
  current_vsa_bias: string;
  actionable: boolean;
  scoring_evidence_age: number | null;
  used_fallback_evidence: boolean;
  supporting_event_codes: string[];
  opposing_event_codes: string[];
  ignored_audit_only_codes: string[];
  reason: string;
  pending_supersession?: boolean;
  supersession_review_confirmed?: boolean;
  supersession_review_blocked?: boolean;
  production_safe: boolean;
};

export type DecisionContext = {
  schema_version: number;
  symbol: string;
  timeframe: string;
  mode: string;
  latest_bar_index: number | null;
  latest_week: string | null;
  qualification: string;
  qualification_lifecycle?: QualificationLifecycle | null;
  actionable: boolean;
  decision: string;
  tradability: string;
  phase: string;
  bias: string;
  confidence: number;
  net_strength: number;
  net_pressure: number;
  reason: string;
  recent_events: DecisionContextEvent[];
  structural_swings: StructuralSwingMemory[];
  story: VSAStorySummary;
  evaluated_at_utc: string;
};

export type { DecisionContextEvent };

type StoryViewMode = "confirmed" | "developing";

type DecisionContextModeStatus = {
  label: string;
  detail: string;
};

const API = process.env.NEXT_PUBLIC_API_URL ?? "http://127.0.0.1:8000";
const NON_VALIDATED_LIFECYCLE_STATUSES = new Set([
  "conflicted",
  "invalidated",
  "expired",
  "needs_follow_through",
  "supersession_review",
]);

export function decisionContextModeStatus(
  mode: string | null | undefined,
): DecisionContextModeStatus {
  const normalized = (mode ?? "confirmed").trim().toLowerCase();
  if (normalized === "developing") {
    return {
      label: "Developing preview",
      detail:
        "Includes the latest available weekly bar and may change before the week closes. Treat this as an early warning, not a confirmed VSA signal.",
    };
  }
  if (normalized === "confirmed") {
    return {
      label: "Confirmed weekly",
      detail:
        "Uses completed weekly bars only. This is the official decision-support context used by the confirmed scanner and journal workflow.",
    };
  }
  return {
    label: pretty(normalized),
    detail:
      "Context mode is not recognized by the frontend. Review the backend payload before treating this story as confirmed.",
  };
}

async function fetchJson<T>(url: string, fallbackError: string): Promise<T> {
  const response = await fetch(url);
  if (response.ok) return (await response.json()) as T;

  let detail = fallbackError;
  try {
    const body = (await response.json()) as { detail?: string };
    if (body.detail) detail = body.detail;
  } catch {
    // Keep the fallback message when the backend did not return JSON.
  }
  throw new Error(detail);
}

function pretty(value: string | null | undefined) {
  if (!value) return "—";
  return value.replaceAll("_", " ").replace(/\b\w/g, (char) => char.toUpperCase());
}

function displayDate(value: string | null | undefined) {
  if (!value) return "—";
  const date = new Date(value);
  return Number.isNaN(date.getTime())
    ? value
    : date.toLocaleDateString("en-IN", {
        day: "2-digit",
        month: "short",
        year: "numeric",
      });
}

function scoreLevel(value: number | null | undefined) {
  if (value === null || value === undefined || Number.isNaN(value)) return "Unknown";
  if (value >= 0.85) return "Exceptional";
  if (value >= 0.70) return "Very strong";
  if (value >= 0.55) return "Strong";
  if (value >= 0.40) return "Moderate";
  if (value >= 0.20) return "Weak";
  return "Very weak";
}

function confidenceMeaning(value: number | null | undefined) {
  if (value === null || value === undefined || Number.isNaN(value)) return "Confidence is not available yet.";
  if (value >= 0.85) return "The story is unusually clear and evidence is highly aligned.";
  if (value >= 0.70) return "The story is clear and evidence is well aligned.";
  if (value >= 0.55) return "The story is constructive but still needs confirmation.";
  if (value >= 0.40) return "The story is mixed; treat it as conditional.";
  if (value >= 0.20) return "The model has limited conviction in this reading.";
  return "The model has very low conviction in this reading.";
}

function pressureMeaning(value: number | null | undefined) {
  if (value === null || value === undefined || Number.isNaN(value)) return "Pressure is not available yet.";
  if (value >= 0.55) return "Demand is clearly in control.";
  if (value >= 0.20) return "Demand is stronger than supply.";
  if (value > -0.20) return "Supply and demand are mixed.";
  if (value > -0.55) return "Supply is stronger than demand.";
  return "Supply is clearly in control.";
}

function evidenceAgeLabel(age: number | null | undefined) {
  if (age === null || age === undefined) return "No current scoring-evidence age";
  if (age === 0) return "Current scoring evidence";
  return `${age} completed bar${age === 1 ? "" : "s"} old`;
}

function codesText(codes: string[] | null | undefined) {
  if (!codes || codes.length === 0) return "None";
  return codes.map((code) => pretty(code)).join(", ");
}

function isPendingSupersession(lifecycle: QualificationLifecycle | null | undefined) {
  return Boolean(lifecycle?.pending_supersession);
}

function isSupersessionReview(lifecycle: QualificationLifecycle | null | undefined) {
  return lifecycle?.status === "supersession_review";
}

function lifecycleStatusLabel(lifecycle: QualificationLifecycle | null | undefined) {
  if (!lifecycle) return "Not available";
  if (isSupersessionReview(lifecycle)) {
    if (lifecycle.supersession_review_blocked) {
      return "Supersession Review · Blocked";
    }
    if (lifecycle.supersession_review_confirmed) {
      return "Supersession Review · Chart-confirmed review";
    }
    return "Supersession Review · Review candidate";
  }
  if (isPendingSupersession(lifecycle)) {
    return `${pretty(lifecycle.status)} · Pending supersession`;
  }
  return pretty(lifecycle.status);
}

function lifecycleStatusDetail(lifecycle: QualificationLifecycle | null | undefined) {
  if (!lifecycle) {
    return "Lifecycle label is not available in this context. Re-run fresh analysis to populate the production-safe label.";
  }

  const side = pretty(lifecycle.qualification_side).toLowerCase();
  const bias = pretty(lifecycle.current_vsa_bias).toLowerCase();

  switch (lifecycle.status) {
    case "active":
      return `The ${side} qualification remains aligned with current production-safe VSA evidence.`;
    case "conflicted":
      if (isPendingSupersession(lifecycle)) {
        return `The ${side} qualification is challenged by current ${bias} production-safe evidence and is pending supersession. Do not treat this as a confirmed ${bias} flip yet.`;
      }
      return `The ${side} qualification is active, but current production-safe VSA evidence is mixed or partly opposing it.`;
    case "supersession_review":
      if (lifecycle.supersession_review_blocked) {
        return `The ${side} qualification reached supersession review, but a blocker remains. Do not treat this as a confirmed ${bias} flip or final invalidation.`;
      }
      return `The ${side} qualification is a chart-confirmed supersession review candidate against current ${bias} evidence. This is review-only: not a confirmed ${bias} flip, not final invalidation, and not detector activation.`;
    case "invalidated":
      return `The previous ${side} qualification is invalidated by current ${bias} production-safe VSA evidence.`;
    case "expired":
      return `The ${side} qualification is stale and should be treated as expired until fresh confirmation appears.`;
    case "needs_follow_through":
      return `The ${side} qualification has not failed, but it still needs follow-through before acting.`;
    case "unqualified":
      return "No persistent bullish or bearish qualification is active.";
    default:
      return `${pretty(lifecycle.status)} status is reported by the backend lifecycle label.`;
  }
}

function lifecycleEvidenceLine(lifecycle: QualificationLifecycle | null | undefined) {
  if (!lifecycle) return "No lifecycle payload was included in this decision context.";
  return [
    `Qualification: ${pretty(lifecycle.qualification)}`,
    `Side: ${pretty(lifecycle.qualification_side)}`,
    `Current VSA bias: ${pretty(lifecycle.current_vsa_bias)}`,
    evidenceAgeLabel(lifecycle.scoring_evidence_age),
  ].join(" · ");
}

function lifecycleFallbackNote(lifecycle: QualificationLifecycle) {
  return lifecycle.used_fallback_evidence
    ? " Fallback scoring evidence is being used, so review freshness before acting."
    : "";
}

function lifecycleAwareHeadline(context: DecisionContext) {
  const lifecycle = context.qualification_lifecycle ?? null;
  if (!lifecycle || !NON_VALIDATED_LIFECYCLE_STATUSES.has(lifecycle.status)) {
    return context.story.headline;
  }

  const side = pretty(lifecycle.qualification_side);
  const phase = pretty(context.phase);

  switch (lifecycle.status) {
    case "expired":
      return `Expired ${side} ${phase} context`;
    case "invalidated":
      return `Invalidated ${side} ${phase} context`;
    case "conflicted":
      if (isPendingSupersession(lifecycle)) {
        return `${side} ${phase} context pending supersession`;
      }
      return `Conflicted ${side} ${phase} context`;
    case "supersession_review":
      return `${side} ${phase} context in supersession review`;
    case "needs_follow_through":
      return `${side} ${phase} context needs follow-through`;
    default:
      return context.story.headline;
  }
}

function lifecycleAwareSummary(context: DecisionContext) {
  const lifecycle = context.qualification_lifecycle ?? null;
  if (!lifecycle || !NON_VALIDATED_LIFECYCLE_STATUSES.has(lifecycle.status)) {
    return context.story.summary;
  }

  const side = pretty(lifecycle.qualification_side).toLowerCase();
  const phase = pretty(context.phase).toLowerCase();
  const bias = pretty(lifecycle.current_vsa_bias).toLowerCase();
  const opposing = lifecycle.opposing_event_codes.length > 0
    ? ` Opposing evidence: ${codesText(lifecycle.opposing_event_codes)}.`
    : "";
  const supporting = lifecycle.supporting_event_codes.length > 0
    ? ` Supporting evidence: ${codesText(lifecycle.supporting_event_codes)}.`
    : "";

  switch (lifecycle.status) {
    case "expired":
      return `Earlier ${side} VSA context still exists in the ${phase} background, but the supporting evidence is stale (${evidenceAgeLabel(lifecycle.scoring_evidence_age).toLowerCase()}). Treat it as expired until fresh confirmation appears instead of treating the old structure as validated.${supporting}${lifecycleFallbackNote(lifecycle)}`;
    case "invalidated":
      return `Earlier ${side} VSA context has been invalidated by current ${bias} production-safe evidence. Wait for a fresh setup before treating the old qualification as validated.${opposing}${lifecycleFallbackNote(lifecycle)}`;
    case "conflicted":
      if (isPendingSupersession(lifecycle)) {
        return `Earlier ${side} VSA context in the ${phase} background is challenged by current ${bias} production-safe evidence and is pending supersession. Do not treat this as a confirmed ${bias} flip yet; wait for follow-through or a new opposite qualification to supersede the old context.${opposing}${supporting}${lifecycleFallbackNote(lifecycle)}`;
      }
      return `Earlier ${side} VSA context is now conflicted. Current production-safe evidence is mixed, so treat the story as conditional until one side confirms.${opposing}${supporting}${lifecycleFallbackNote(lifecycle)}`;
    case "supersession_review":
      if (lifecycle.supersession_review_blocked) {
        return `Earlier ${side} VSA context in the ${phase} background reached supersession review, but a blocker remains. Treat this as review-only until the blocker clears; do not mark it as a confirmed ${bias} flip, final invalidation, or activated detector signal.${opposing}${supporting}${lifecycleFallbackNote(lifecycle)}`;
      }
      return `Earlier ${side} VSA context in the ${phase} background is now a chart-confirmed supersession review candidate against current ${bias} evidence. This is a conservative review state only: it highlights that the old context may be superseded, but it is not a confirmed ${bias} flip, not final invalidation, and not detector activation.${opposing}${supporting}${lifecycleFallbackNote(lifecycle)}`;
    case "needs_follow_through":
      return `Earlier ${side} VSA context has not failed, but it still needs follow-through. Wait for fresh confirmation before upgrading the story from background context to validated signal.${supporting}${lifecycleFallbackNote(lifecycle)}`;
    default:
      return context.story.summary;
  }
}

function lifecycleDetailClass(lifecycle: QualificationLifecycle | null | undefined) {
  const status = lifecycle?.status ?? "unavailable";
  const caution = NON_VALIDATED_LIFECYCLE_STATUSES.has(status) ? "caution" : "current";
  return `evidence-detail lifecycle-detail lifecycle-detail-${status} lifecycle-detail-${caution}`;
}

function isBullish(value: string) {
  const text = value.toLowerCase();
  return text.includes("bull") || text.includes("demand") || text.includes("accumulation") || text.includes("markup");
}

type DecisionContextPanelProps = {
  context: DecisionContext | null | undefined;
  onSelectEvent?: (event: DecisionContextEvent) => void;
};

export function DecisionContextPanel({
  context,
  onSelectEvent,
}: DecisionContextPanelProps) {
  const requestGenerationRef = useRef(0);
  const [storyViewMode, setStoryViewMode] = useState<StoryViewMode>("confirmed");
  const [developingContext, setDevelopingContext] = useState<DecisionContext | null>(null);
  const [developingContextError, setDevelopingContextError] = useState("");
  const [developingContextLoading, setDevelopingContextLoading] = useState(false);
  const [legendRegistry, setLegendRegistry] = useState<LegendRegistryPayload | null>(null);
  const [legendRegistryError, setLegendRegistryError] = useState("");

  useEffect(() => {
    requestGenerationRef.current += 1;
    setStoryViewMode("confirmed");
    setDevelopingContext(null);
    setDevelopingContextError("");
    setDevelopingContextLoading(false);
  }, [context?.symbol, context?.timeframe, context?.latest_week]);

  useEffect(() => {
    let cancelled = false;
    setLegendRegistryError("");

    fetchJson<LegendRegistryPayload>(
      `${API}/api/vsa/legends`,
      "Plain-English legend registry failed",
    )
      .then((payload) => {
        if (!cancelled) setLegendRegistry(payload);
      })
      .catch((err) => {
        if (!cancelled) {
          setLegendRegistry(null);
          setLegendRegistryError(
            err instanceof Error ? err.message : "Plain-English legend registry failed",
          );
        }
      });

    return () => {
      cancelled = true;
    };
  }, []);

  const legendLookup = useMemo(
    () => buildPlainEnglishLegendLookup(legendRegistry?.legends ?? []),
    [legendRegistry],
  );

  async function loadDevelopingContext() {
    if (!context) return;

    const requestGeneration = requestGenerationRef.current;
    const encodedSymbol = encodeURIComponent(context.symbol);
    setDevelopingContextLoading(true);
    setDevelopingContextError("");

    try {
      const preview = await fetchJson<DecisionContext>(
        `${API}/api/symbols/${encodedSymbol}/decision-context/developing`,
        "Developing context failed",
      );
      if (requestGeneration !== requestGenerationRef.current) return;
      setDevelopingContext(preview);
      setStoryViewMode("developing");
    } catch (err) {
      if (requestGeneration !== requestGenerationRef.current) return;
      setDevelopingContext(null);
      setStoryViewMode("confirmed");
      setDevelopingContextError(err instanceof Error ? err.message : "Developing context failed");
    } finally {
      if (requestGeneration === requestGenerationRef.current) {
        setDevelopingContextLoading(false);
      }
    }
  }

  function showConfirmedContext() {
    setStoryViewMode("confirmed");
    setDevelopingContextError("");
  }

  if (!context) {
    return (
      <section className="structure-workspace readable-single-section">
        <div className="panel structure-summary">
          <span className="section-kicker">VSA STORY</span>
          <h2>No story yet</h2>
          <p>Run analysis to build the compact decision context.</p>
        </div>
      </section>
    );
  }

  const activeContext = storyViewMode === "developing" && developingContext ? developingContext : context;
  const latestEvents = activeContext.recent_events.slice().reverse().slice(0, 6);
  const positivePressure = activeContext.net_pressure >= 0;
  const modeStatus = decisionContextModeStatus(activeContext.mode);
  const lifecycle = activeContext.qualification_lifecycle ?? null;

  function eventPlainEnglish(event: DecisionContextEvent) {
    return (
      plainEnglishLegendText(legendLookup, { code: event.code, family: "event_label" }) ??
      plainEnglishLegendText(legendLookup, { code: event.code }) ??
      event.description ??
      event.observation
    );
  }

  return (
    <section className="readable-story-grid">
      <div className="panel structure-summary readable-story-main">
        <span className="section-kicker">VSA STORY</span>
        <div className="context-mode-switch" aria-label="Decision context mode controls">
          <button
            type="button"
            className={storyViewMode === "confirmed" ? "selected" : ""}
            aria-pressed={storyViewMode === "confirmed"}
            onClick={showConfirmedContext}
          >
            Confirmed weekly
          </button>
          <button
            type="button"
            className={storyViewMode === "developing" ? "selected developing" : ""}
            aria-pressed={storyViewMode === "developing"}
            disabled={developingContextLoading}
            onClick={() => void loadDevelopingContext()}
          >
            {developingContextLoading ? "Loading preview..." : "Developing preview"}
          </button>
        </div>
        {developingContextError ? (
          <div className="evidence-detail" role="alert">
            <h4>Developing preview unavailable</h4>
            <p>{developingContextError}</p>
          </div>
        ) : null}
        <h2>{lifecycleAwareHeadline(activeContext)}</h2>
        <p className="story-summary-readable">{lifecycleAwareSummary(activeContext)}</p>
        <div className="mode-explainer" aria-label={`${modeStatus.label} context mode`}>
          <strong>{modeStatus.label}</strong>
          <span>{modeStatus.detail}</span>
        </div>
        <div className="summary-grid readable-summary-grid story-lifecycle-summary-grid">
          <span>
            Phase
            <strong>{pretty(activeContext.phase)}</strong>
          </span>
          <span>
            Tradability
            <strong>{pretty(activeContext.tradability)}</strong>
          </span>
          <span>
            Bias
            <strong>{pretty(activeContext.bias)}</strong>
          </span>
          <span>
            Qualification lifecycle
            <strong>{lifecycleStatusLabel(lifecycle)}</strong>
            <small>{lifecycleStatusDetail(lifecycle)}</small>
          </span>
        </div>
        <div className={lifecycleDetailClass(lifecycle)} aria-label="Qualification lifecycle detail">
          <h4>Qualification lifecycle</h4>
          <p>{lifecycleStatusDetail(lifecycle)}</p>
          <small>{lifecycleEvidenceLine(lifecycle)}</small>
          {lifecycle ? (
            <>
              <small>
                Opposing evidence: {codesText(lifecycle.opposing_event_codes)}. Supporting evidence:{" "}
                {codesText(lifecycle.supporting_event_codes)}.
              </small>
              {isSupersessionReview(lifecycle) ? (
                <small>
                  Supersession review: chart-confirmed review candidate only. Not a bullish flip,
                  final invalidation, or detector activation.
                </small>
              ) : null}
              {isPendingSupersession(lifecycle) ? (
                <small>
                  Pending supersession: the old qualification is challenged, but the scanner has not
                  confirmed a new opposite qualification.
                </small>
              ) : null}
              {lifecycle.ignored_audit_only_codes.length > 0 ? (
                <small>
                  Audit-only candidates ignored for this production-safe label:{" "}
                  {codesText(lifecycle.ignored_audit_only_codes)}.
                </small>
              ) : null}
              {lifecycle.used_fallback_evidence ? (
                <small>Uses fallback scoring evidence; review freshness before acting.</small>
              ) : null}
              {!lifecycle.production_safe ? (
                <small>This lifecycle payload is marked not production-safe by the backend.</small>
              ) : null}
            </>
          ) : null}
        </div>
        <div className="plain-score story-plain-reading">
          <span>Pressure</span>
          <strong>{positivePressure ? "Demand" : "Supply"}</strong>
          <small>{pressureMeaning(activeContext.net_pressure)}</small>
        </div>
        <div className="plain-score story-plain-reading">
          <span>Confidence</span>
          <strong>{scoreLevel(activeContext.confidence)}</strong>
          <small>{confidenceMeaning(activeContext.confidence)} Evaluated {displayDate(activeContext.evaluated_at_utc)}.</small>
        </div>
      </div>

      <div className="panel structure-sequence story-watch-panel">
        <div className="workspace-heading">
          <div>
            <span className="section-kicker">WHAT TO WATCH NEXT</span>
            <h2>Confirmation and invalidation</h2>
          </div>
          <span>{modeStatus.label}</span>
        </div>
        <div className="evidence-detail latest-evidence">
          <h4>Confirmation</h4>
          <p>{activeContext.story.confirmation_condition}</p>
          <h4>Invalidation</h4>
          <p>{activeContext.story.invalidation_condition}</p>
        </div>
        <div className="vsa-category-summary expected-next-behavior">
          <span className="section-kicker">EXPECTED NEXT BEHAVIOR</span>
          <div className="vsa-category-list">
            {activeContext.story.what_to_expect_next.map((item) => (
              <span key={item}>{item}</span>
            ))}
          </div>
        </div>
      </div>

      <div className="panel structure-sequence">
        <div className="workspace-heading">
          <div>
            <span className="section-kicker">RECENT SMART-MONEY EVIDENCE</span>
            <h2>Bar-by-bar story events</h2>
          </div>
          <span>{latestEvents.length} shown</span>
        </div>
        {legendRegistryError ? (
          <p className="signal-code">Plain-English legend registry unavailable: {legendRegistryError}</p>
        ) : null}
        {latestEvents.length === 0 ? (
          <p>No recent decision events are stored yet.</p>
        ) : (
          latestEvents.map((event) => {
            const bullish = isBullish(event.direction);
            const legendText = eventPlainEnglish(event);
            return (
              <button
                type="button"
                className="signal"
                key={`${event.bar_index}-${event.code}-${event.role}`}
                onClick={() => onSelectEvent?.(event)}
              >
                <div className="signal-top">
                  <span className={bullish ? "dot up" : "dot down"} />
                  <strong>{pretty(event.code)}</strong>
                  <span>{scoreLevel(event.strength)}</span>
                </div>
                <div className="signal-code">
                  {displayDate(event.week)} · {pretty(event.category)} · {pretty(event.role)}
                </div>
                <p>{event.observation}</p>
                <small>Plain-English meaning: {legendText}</small>
              </button>
            );
          })
        )}
      </div>
    </section>
  );
}
