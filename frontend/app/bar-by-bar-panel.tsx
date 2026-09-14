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

type AuditEventRow = {
  replay_week: string;
  target_event_codes?: string[];
  vsa_event_codes?: string[];
  detector_diagnostics?: string[];
  notes?: string[];
};

type AuditSymbolResult = {
  rows?: AuditEventRow[];
};

type AuditEventsResponse = {
  results?: AuditSymbolResult[];
};

type SelectedWeekDetectorEvent = {
  code: string;
  week: string;
  notes: string[];
  diagnostics: string[];
};

type ApiErrorBody = {
  detail?: string;
};

const READ_ONLY_DETECTOR_CODE_LABELS: Record<string, string> = {
  effort_gt_result: "Effort > Result",
  result_gt_effort: "Result > Effort",
  absorption: "Absorption",
};

const READ_ONLY_DETECTOR_CODES = new Set(Object.keys(READ_ONLY_DETECTOR_CODE_LABELS));

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

function auditWeekParam(value: string) {
  return value.trim().slice(0, 10);
}

function normalizeDetectorCode(code: string) {
  return code.trim().toLowerCase();
}

function detectorCodeLabel(code: string) {
  return READ_ONLY_DETECTOR_CODE_LABELS[normalizeDetectorCode(code)] ?? code;
}

function detectorReading(event: SelectedWeekDetectorEvent) {
  if (event.notes.length > 0) return event.notes.join(" ");
  if (event.diagnostics.length > 0) return event.diagnostics.join(" · ");
  return "Historical audit detected this read-only event for the selected week.";
}

function selectedWeekDetectorEventsFromAudit(
  payload: AuditEventsResponse,
  selectedWeek: string,
): SelectedWeekDetectorEvent[] {
  const selectedWeekParam = auditWeekParam(selectedWeek);
  const rows = (payload.results ?? []).flatMap((result) => result.rows ?? []);
  const row = rows.find((item) => auditWeekParam(item.replay_week) === selectedWeekParam);
  if (!row) return [];

  const detectorCodes = Array.from(
    new Set([...(row.target_event_codes ?? []), ...(row.vsa_event_codes ?? [])].map(normalizeDetectorCode)),
  ).filter((code) => READ_ONLY_DETECTOR_CODES.has(code));

  return detectorCodes.map((code) => ({
    code,
    week: row.replay_week,
    notes: row.notes ?? [],
    diagnostics: row.detector_diagnostics ?? [],
  }));
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
  const [selectedWeekDetectorEvidence, setSelectedWeekDetectorEvidence] = useState<SelectedWeekDetectorEvent[]>([]);
  const [localSelectedWeek, setLocalSelectedWeek] = useState<string | null>(null);
  const [error, setError] = useState("");
  const [detectorError, setDetectorError] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [isDetectorLoading, setIsDetectorLoading] = useState(false);

  useEffect(() => {
    let cancelled = false;
    const encodedSymbol = encodeURIComponent(symbol);
    setIsLoading(true);
    setError("");
    setResponse(null);
    setSelectedWeekDetectorEvidence([]);
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
  const selectedReadingWeek = selectedReading?.week ?? null;

  useEffect(() => {
    if (!selectedReadingWeek) {
      setSelectedWeekDetectorEvidence([]);
      setDetectorError("");
      setIsDetectorLoading(false);
      return;
    }

    const selectedWeekForAudit = selectedReadingWeek;
    let cancelled = false;
    const encodedSymbol = encodeURIComponent(symbol);
    const encodedStartWeek = encodeURIComponent(auditWeekParam(selectedWeekForAudit));
    setIsDetectorLoading(true);
    setDetectorError("");
    setSelectedWeekDetectorEvidence([]);

    async function loadSelectedWeekDetectorEvidence() {
      try {
        const payload = await fetchJson<AuditEventsResponse>(
          `${API}/api/vsa-audit/events?symbols=${encodedSymbol}&start_week=${encodedStartWeek}&horizon_weeks=1`,
          "Selected-week detector evidence failed",
        );
        if (!cancelled) {
          setSelectedWeekDetectorEvidence(selectedWeekDetectorEventsFromAudit(payload, selectedWeekForAudit));
        }
      } catch (err) {
        if (!cancelled) {
          setDetectorError(err instanceof Error ? err.message : "Selected-week detector evidence failed");
        }
      } finally {
        if (!cancelled) setIsDetectorLoading(false);
      }
    }

    void loadSelectedWeekDetectorEvidence();
    return () => {
      cancelled = true;
    };
  }, [symbol, selectedReadingWeek]);

  function selectReading(item: WeeklyBarReading) {
    setLocalSelectedWeek(item.week);
    onSelectWeek?.(item.week);
  }

  function renderSelectedWeekDetectorEvidence() {
    if (!selectedReading) return null;

    return (
      <div className={styles.selectedWeekDetectorEvidence}>
        <h4>Read-only Detector Evidence</h4>
        <small className={styles.selectedWeekDetectorGuardrail}>
          Selected-week detector evidence comes from the historical audit endpoint and is review-only. It does not change scoring, ranking, actionability, trade plan, alerts, or orders.
        </small>
        {isDetectorLoading && <small>Loading selected-week audit evidence...</small>}
        {!isDetectorLoading && detectorError && <small>Selected-week audit evidence unavailable: {detectorError}</small>}
        {!isDetectorLoading && !detectorError && selectedWeekDetectorEvidence.length === 0 && (
          <small>No Effort/Result or Absorption event in the historical audit response for this selected week.</small>
        )}
        {!isDetectorLoading && !detectorError && selectedWeekDetectorEvidence.length > 0 && (
          <ul className={styles.selectedWeekDetectorList}>
            {selectedWeekDetectorEvidence.map((event) => (
              <li className={styles.selectedWeekDetectorItem} key={`${event.week}-${event.code}`}>
                <span className={styles.readOnlyDetectorBadge}>Read-only / not scoring</span>
                <strong>{detectorCodeLabel(event.code)}</strong>
                <p>{detectorReading(event)}</p>
                <small>Historical audit · {displayDate(event.week)}</small>
              </li>
            ))}
          </ul>
        )}
      </div>
    );
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
              {renderSelectedWeekDetectorEvidence()}
            </article>
          )}
        </div>
      )}
    </section>
  );
}