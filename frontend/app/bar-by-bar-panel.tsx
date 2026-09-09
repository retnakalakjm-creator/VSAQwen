"use client";

import { useEffect, useMemo, useState } from "react";
import styles from "./bar-by-bar-panel.module.css";

const API = process.env.NEXT_PUBLIC_API_URL ?? "http://127.0.0.1:8000";
const DEFAULT_LOOKBACK = 15;

type WeeklyBarReading = {
  week: string;
  professional_reading: string;
};

type WeeklyBarReadingsResponse = {
  symbol: string;
  timeframe: string;
  latest_week: string;
  lookback: number;
  readings: WeeklyBarReading[];
};

type ApiErrorBody = {
  detail?: string;
};

type BarByBarPanelProps = {
  symbol: string;
  lookback?: number;
  selectedWeek?: string | null;
  onSelectWeek?: (week: string | null) => void;
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

function shortDate(value: string | undefined | null) {
  if (!value) return "—";
  const date = new Date(value);
  return Number.isNaN(date.getTime())
    ? value
    : date.toLocaleDateString("en-IN", {
        day: "2-digit",
        month: "short",
      });
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

export function BarByBarPanel({
  symbol,
  lookback = DEFAULT_LOOKBACK,
  selectedWeek,
  onSelectWeek,
}: BarByBarPanelProps) {
  const [response, setResponse] = useState<WeeklyBarReadingsResponse | null>(null);
  const [localSelectedWeek, setLocalSelectedWeek] = useState<string | null>(null);
  const [error, setError] = useState("");
  const [isLoading, setIsLoading] = useState(false);

  useEffect(() => {
    let cancelled = false;
    const encodedSymbol = encodeURIComponent(symbol);
    setIsLoading(true);
    setError("");
    setResponse(null);
    setLocalSelectedWeek(null);
    onSelectWeek?.(null);

    async function loadReadings() {
      try {
        const payload = await fetchJson<WeeklyBarReadingsResponse>(
          `${API}/api/symbols/${encodedSymbol}/weekly-bar-readings?lookback=${lookback}`,
          "Weekly bar readings failed",
        );
        if (!cancelled) {
          const latestWeek = payload.readings.at(-1)?.week ?? null;
          setResponse(payload);
          setLocalSelectedWeek(latestWeek);
          onSelectWeek?.(latestWeek);
        }
      } catch (err) {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : "Weekly bar readings failed");
        }
      } finally {
        if (!cancelled) setIsLoading(false);
      }
    }

    void loadReadings();
    return () => {
      cancelled = true;
    };
  }, [symbol, lookback, onSelectWeek]);

  const readings = response?.readings ?? [];
  const selectedReading = useMemo(() => {
    const targetWeek = selectedWeek ?? localSelectedWeek;
    return readings.find((item) => item.week === targetWeek) ?? readings.at(-1) ?? null;
  }, [localSelectedWeek, readings, selectedWeek]);

  function selectReading(item: WeeklyBarReading) {
    setLocalSelectedWeek(item.week);
    onSelectWeek?.(item.week);
  }

  return (
    <section className={`panel bar-story-card api-bar-reading-panel ${styles.compactBarReadingPanel}`}>
      <div className="workspace-heading">
        <div>
          <span className="section-kicker">BAR-BY-BAR INTERPRETATION</span>
          <h2>Weekly professional reading</h2>
        </div>
        <span>{response ? `${readings.length} weeks` : isLoading ? "Loading" : "API"}</span>
      </div>

      {isLoading && <div className="status">Loading weekly Bar-by-Bar readings...</div>}
      {error && <div className="status error-status">{error}</div>}

      {!isLoading && !error && readings.length === 0 && (
        <div className="status">No weekly readings are available yet.</div>
      )}

      {readings.length > 0 && (
        <div className={styles.barReadingWorkspace}>
          <div className={styles.barReadingRailWrap}>
            <div className={styles.barReadingRailHeading}>
              <span>Week</span>
              <small>Oldest → latest</small>
            </div>
            <div className={styles.barReadingRail} role="list" aria-label="Completed weekly bars">
              {readings.map((item, index) => {
                const isSelected = selectedReading?.week === item.week;
                const isLatest = index === readings.length - 1;
                return (
                  <button
                    type="button"
                    className={`${styles.barReadingChip} ${isSelected ? styles.selected : ""}`}
                    key={item.week}
                    role="listitem"
                    aria-pressed={isSelected}
                    onClick={() => selectReading(item)}
                  >
                    <span>{shortDate(item.week)}</span>
                    {isLatest && <small>Latest</small>}
                  </button>
                );
              })}
            </div>
          </div>

          {selectedReading && (
            <article className={`selected-bar-reading ${styles.selectedBarReadingFocus}`}>
              <span className="section-kicker">Week</span>
              <h3>{displayDate(selectedReading.week)}</h3>
              <h4>Professional Reading</h4>
              <p>{selectedReading.professional_reading}</p>
            </article>
          )}
        </div>
      )}
    </section>
  );
}
