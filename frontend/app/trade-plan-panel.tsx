"use client";

import { useEffect, useState } from "react";

const API = process.env.NEXT_PUBLIC_API_URL ?? "http://127.0.0.1:8000";

type TradePlanLevel = {
  label: string;
  price: number | null;
  lower: number | null;
  upper: number | null;
  source: string;
  note: string;
};

type TradePlan = {
  posture: string;
  setup_type: string;
  reference_price: number | null;
  support: TradePlanLevel;
  resistance: TradePlanLevel;
  entry_condition: string;
  confirmation_trigger: string;
  invalidation_condition: string;
  risk_reading: string;
  reward_reading: string;
  notes: string[];
  analysis_only: boolean;
};

type TradePlanResponse = {
  symbol: string;
  timeframe: string;
  latest_week: string;
  plan: TradePlan;
};

type ApiErrorBody = {
  detail?: string;
};

type TradePlanPanelProps = {
  symbol: string;
};

function displayDate(value: string | undefined | null) {
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

function price(value: number | null | undefined) {
  return typeof value === "number" && Number.isFinite(value) ? value.toFixed(2) : "—";
}

function levelArea(level: TradePlanLevel) {
  if (level.lower === null || level.upper === null) return "Area not available";
  return `${price(level.lower)} – ${price(level.upper)}`;
}

async function fetchJson<T>(url: string, fallbackError: string): Promise<T> {
  const response = await fetch(url);
  if (response.ok) return (await response.json()) as T;

  let detail = fallbackError;
  try {
    const body = (await response.json()) as ApiErrorBody;
    if (body.detail) detail = body.detail;
  } catch {
    // Keep fallback when the backend did not return JSON.
  }
  throw new Error(detail);
}

function LevelCard({ title, level }: { title: string; level: TradePlanLevel }) {
  return (
    <div className="trade-level-card">
      <span className="section-kicker">{title}</span>
      <h3>{level.label}</h3>
      <strong>{price(level.price)}</strong>
      <small>{levelArea(level)}</small>
      <p>{level.source}</p>
      <em>{level.note}</em>
    </div>
  );
}

export function TradePlanPanel({ symbol }: TradePlanPanelProps) {
  const [response, setResponse] = useState<TradePlanResponse | null>(null);
  const [error, setError] = useState("");
  const [isLoading, setIsLoading] = useState(false);

  useEffect(() => {
    let cancelled = false;
    const encodedSymbol = encodeURIComponent(symbol);
    setIsLoading(true);
    setError("");
    setResponse(null);

    async function loadTradePlan() {
      try {
        const payload = await fetchJson<TradePlanResponse>(
          `${API}/api/symbols/${encodedSymbol}/trade-plan`,
          "Trade plan failed",
        );
        if (!cancelled) setResponse(payload);
      } catch (err) {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : "Trade plan failed");
        }
      } finally {
        if (!cancelled) setIsLoading(false);
      }
    }

    void loadTradePlan();
    return () => {
      cancelled = true;
    };
  }, [symbol]);

  if (isLoading) return <div className="status readable-status">Loading analysis-only trade plan...</div>;
  if (error) return <div className="status error-status">{error}</div>;
  if (!response) return <div className="status readable-status">Trade plan is not available yet.</div>;

  const plan = response.plan;

  return (
    <section className="readable-stack trade-plan-workspace">
      <div className="panel trade-plan-hero">
        <div className="workspace-heading">
          <div>
            <span className="section-kicker">ANALYSIS-ONLY TRADE PLAN</span>
            <h2>{plan.posture}</h2>
          </div>
          <span>{response.timeframe} · {displayDate(response.latest_week)}</span>
        </div>
        <p>{plan.setup_type}</p>
        <div className="trade-plan-badges">
          <span>Reference price: {price(plan.reference_price)}</span>
          <span>{plan.analysis_only ? "Analysis-only" : "Review required"}</span>
          <span>Not an order signal</span>
        </div>
      </div>

      <div className="trade-plan-grid">
        <LevelCard title="SUPPORT CONTEXT" level={plan.support} />
        <LevelCard title="RESISTANCE CONTEXT" level={plan.resistance} />
      </div>

      <div className="panel trade-plan-checklist">
        <div className="workspace-heading">
          <div>
            <span className="section-kicker">PLANNING CONDITIONS</span>
            <h2>What must happen next</h2>
          </div>
        </div>
        <div className="trade-plan-row">
          <span>Entry condition</span>
          <p>{plan.entry_condition}</p>
        </div>
        <div className="trade-plan-row">
          <span>Confirmation trigger</span>
          <p>{plan.confirmation_trigger}</p>
        </div>
        <div className="trade-plan-row">
          <span>Invalidation condition</span>
          <p>{plan.invalidation_condition}</p>
        </div>
        <div className="trade-plan-row">
          <span>Risk reading</span>
          <p>{plan.risk_reading}</p>
        </div>
        <div className="trade-plan-row">
          <span>Reward reading</span>
          <p>{plan.reward_reading}</p>
        </div>
      </div>

      <div className="panel trade-plan-notes">
        <span className="section-kicker">BOUNDARY</span>
        <h2>Decision support only</h2>
        {plan.notes.length === 0 ? (
          <p>This plan is analysis-only and must not be treated as broker/order/account instruction.</p>
        ) : (
          <ul>
            {plan.notes.map((note) => <li key={note}>{note}</li>)}
          </ul>
        )}
      </div>
    </section>
  );
}
