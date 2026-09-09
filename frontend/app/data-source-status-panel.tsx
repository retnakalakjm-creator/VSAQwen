"use client";

import { useEffect, useState } from "react";

type DataSourceStatus = {
  symbol: string;
  configured_provider: string;
  active_provider: string;
  cache_available: boolean;
  cache_source: string | null;
  cache_format: string | null;
  cache_rows: number | null;
  cache_first_date: string | null;
  cache_last_date: string | null;
  cache_updated_at_utc: string | null;
  stale_cache: boolean;
  stale_reason: string | null;
  upstox_enabled: boolean | null;
  upstox_token_env: string | null;
  upstox_token_present: boolean | null;
  upstox_symbol_mapped: boolean | null;
  diagnostic_only: boolean;
};

const API = process.env.NEXT_PUBLIC_API_URL ?? "http://127.0.0.1:8000";

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

function displayDateTime(value: string | null | undefined) {
  if (!value) return "—";
  const date = new Date(value);
  return Number.isNaN(date.getTime())
    ? value
    : date.toLocaleString("en-IN", {
        day: "2-digit",
        month: "short",
        year: "numeric",
        hour: "2-digit",
        minute: "2-digit",
      });
}

function yesNo(value: boolean | null | undefined) {
  if (value === null || value === undefined) return "—";
  return value ? "Yes" : "No";
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

type DataSourceStatusPanelProps = {
  symbol: string;
};

export function DataSourceStatusPanel({ symbol }: DataSourceStatusPanelProps) {
  const [status, setStatus] = useState<DataSourceStatus | null>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    const normalizedSymbol = symbol.trim().toUpperCase();
    if (!normalizedSymbol) {
      setStatus(null);
      setError("");
      setLoading(false);
      return;
    }

    let cancelled = false;
    setLoading(true);
    setError("");

    async function loadStatus() {
      try {
        const payload = await fetchJson<DataSourceStatus>(
          `${API}/api/symbols/${encodeURIComponent(normalizedSymbol)}/data-source`,
          "Data source status failed",
        );
        if (!cancelled) setStatus(payload);
      } catch (err) {
        if (!cancelled) {
          setStatus(null);
          setError(err instanceof Error ? err.message : "Data source status failed");
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    }

    void loadStatus();
    return () => {
      cancelled = true;
    };
  }, [symbol]);

  const hasUpstoxStatus = status?.upstox_enabled !== null && status?.upstox_enabled !== undefined;

  return (
    <section className="structure-workspace" aria-label="Data source and cache freshness">
      <div className="panel structure-summary">
        <span className="section-kicker">DATA SOURCE</span>
        <h2>{loading ? "Checking source…" : pretty(status?.active_provider)}</h2>
        {error ? (
          <p>{error}</p>
        ) : (
          <>
            <p>
              {status?.diagnostic_only
                ? "Diagnostic-only provider/cache status. No market-data download or scanner refresh is triggered by this panel."
                : "Provider status is unavailable."}
            </p>
            <div className="summary-grid">
              <span>
                Provider
                <strong>{pretty(status?.configured_provider)}</strong>
              </span>
              <span>
                Cache
                <strong>{status?.cache_available ? "Available" : "Missing"}</strong>
              </span>
              <span>
                Source
                <strong>{pretty(status?.cache_source)}</strong>
              </span>
            </div>
          </>
        )}
      </div>

      <div className="panel structure-sequence">
        <div className="workspace-heading">
          <div>
            <span className="section-kicker">CACHE FRESHNESS</span>
            <h2>{status?.stale_cache ? "Stale cache warning" : "Latest cache metadata"}</h2>
          </div>
          <span>{status?.cache_rows ?? "—"} rows</span>
        </div>
        <div className="evidence-detail latest-evidence">
          <h4>Cached range</h4>
          <p>
            {displayDate(status?.cache_first_date)} → {displayDate(status?.cache_last_date)}
          </p>
          <h4>Updated</h4>
          <p>{displayDateTime(status?.cache_updated_at_utc)}</p>
          {status?.stale_cache && (
            <>
              <h4>Stale reason</h4>
              <p>{status.stale_reason}</p>
            </>
          )}
        </div>
      </div>

      {hasUpstoxStatus && (
        <div className="panel structure-sequence">
          <div className="workspace-heading">
            <div>
              <span className="section-kicker">UPSTOX READINESS</span>
              <h2>Read-only provider checks</h2>
            </div>
            <span>{status?.upstox_enabled ? "Enabled" : "Disabled"}</span>
          </div>
          <div className="summary-grid">
            <span>
              Token env
              <strong>{status?.upstox_token_env ?? "—"}</strong>
            </span>
            <span>
              Token present
              <strong>{yesNo(status?.upstox_token_present)}</strong>
            </span>
            <span>
              Symbol mapped
              <strong>{yesNo(status?.upstox_symbol_mapped)}</strong>
            </span>
          </div>
          <p>
            Token values, account data, orders, holdings, funds, margins, and positions are not requested or shown.
          </p>
        </div>
      )}
    </section>
  );
}
