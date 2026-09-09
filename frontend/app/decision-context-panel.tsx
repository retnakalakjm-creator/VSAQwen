"use client";

import { useEffect, useRef, useState } from "react";

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

export type DecisionContext = {
  schema_version: number;
  symbol: string;
  timeframe: string;
  mode: string;
  latest_bar_index: number | null;
  latest_week: string | null;
  qualification: string;
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

function score(value: number) {
  return value.toFixed(2);
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

  useEffect(() => {
    requestGenerationRef.current += 1;
    setStoryViewMode("confirmed");
    setDevelopingContext(null);
    setDevelopingContextError("");
    setDevelopingContextLoading(false);
  }, [context?.symbol, context?.timeframe, context?.latest_week]);

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
      <section className="structure-workspace">
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
  const latestSwings = activeContext.structural_swings.slice(-4);
  const positivePressure = activeContext.net_pressure >= 0;
  const modeStatus = decisionContextModeStatus(activeContext.mode);

  return (
    <section className="structure-workspace">
      <div className="panel structure-summary">
        <span className="section-kicker">VSA STORY</span>
        <div
          className="chart-tools"
          aria-label="Decision context mode controls"
          style={{ justifyContent: "flex-start", margin: "0 0 8px" }}
        >
          <button
            type="button"
            aria-pressed={storyViewMode === "confirmed"}
            disabled={storyViewMode === "confirmed"}
            onClick={showConfirmedContext}
          >
            Confirmed weekly
          </button>
          <button
            type="button"
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
        <h2>{activeContext.story.headline}</h2>
        <p>{activeContext.story.summary}</p>
        <div className="evidence-detail latest-evidence" aria-label={`${modeStatus.label} context mode`}>
          <h4>{modeStatus.label}</h4>
          <p>{modeStatus.detail}</p>
        </div>
        <div className="summary-grid">
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
        </div>
        <div className="plain-score">
          <span>Pressure</span>
          <strong>{positivePressure ? "Demand" : "Supply"}</strong>
          <small>{score(activeContext.net_pressure)} net pressure</small>
        </div>
        <div className="plain-score">
          <span>Confidence</span>
          <strong>{score(activeContext.confidence)}</strong>
          <small>Evaluated {displayDate(activeContext.evaluated_at_utc)}</small>
        </div>
      </div>

      <div className="panel structure-sequence">
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
        <div className="vsa-category-summary">
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
        {latestEvents.length === 0 ? (
          <p>No recent decision events are stored yet.</p>
        ) : (
          latestEvents.map((event) => {
            const bullish = isBullish(event.direction);
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
                  <span>{score(event.strength)}</span>
                </div>
                <div className="signal-code">
                  {displayDate(event.week)} · {pretty(event.category)} · {pretty(event.role)}
                </div>
                <p>{event.observation}</p>
              </button>
            );
          })
        )}
      </div>

      <div className="panel structure-sequence">
        <div className="workspace-heading">
          <div>
            <span className="section-kicker">STRUCTURE MEMORY</span>
            <h2>Recent decisive swings</h2>
          </div>
          <span>{latestSwings.length} stored</span>
        </div>
        <div className="swing-track">
          {latestSwings.map((swing, index) => {
            const high = swing.type.toLowerCase().includes("high");
            return (
              <div
                className={`swing-node ${high ? "high" : "low"} ${index === latestSwings.length - 1 ? "latest" : ""}`}
                key={`${swing.pivot_bar_index}-${swing.type}`}
              >
                <span>{swing.label ?? swing.type}</span>
                <small>{swing.price.toFixed(0)}</small>
                <em>{swing.grade}</em>
                {index < latestSwings.length - 1 && <b aria-hidden="true">→</b>}
              </div>
            );
          })}
        </div>
      </div>
    </section>
  );
}
