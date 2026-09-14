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

type AnalysisEvidence = {
  code: string;
  category: string;
  direction: string;
  bar_index: number;
  week: string;
  observation: string;
  description: string;
};

type AnalysisResponse = {
  evidence: AnalysisEvidence[];
};

type ReadOnlyDetectorFamilyKey = "effort_result" | "absorption";

type ReadOnlyDetectorFamily = {
  key: ReadOnlyDetectorFamilyKey;
  title: string;
  helper: string;
  codes: readonly string[];
};

type ApiErrorBody = {
  detail?: string;
};

const READ_ONLY_DETECTOR_FAMILIES: readonly ReadOnlyDetectorFamily[] = [
  {
    key: "effort_result",
    title: "Effort / Result",
    helper: "Backend observations comparing volume effort against price result.",
    codes: ["effort_gt_result", "result_gt_effort"],
  },
  {
    key: "absorption",
    title: "Absorption",
    helper: "Backend absorption observations exposed for review visibility only.",
    codes: ["absorption"],
  },
];

const READ_ONLY_DETECTOR_CODE_LABELS: Record<string, string> = {
  effort_gt_result: "Effort > Result",
  result_gt_effort: "Result > Effort",
  absorption: "Absorption",
};

const READ_ONLY_DETECTOR_CODES = new Set(
  READ_ONLY_DETECTOR_FAMILIES.flatMap((family) => family.codes),
);

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

function normalizeDetectorCode(code: string) {
  return code.trim().toLowerCase();
}

function detectorCodeLabel(code: string) {
  return READ_ONLY_DETECTOR_CODE_LABELS[normalizeDetectorCode(code)] ?? code;
}

function detectorReading(event: AnalysisEvidence) {
  return event.observation || event.description || "Read-only detector evidence is available for this bar.";
}

function readOnlyDetectorEvidence(events: AnalysisEvidence[]) {
  return events.filter((event) => READ_ONLY_DETECTOR_CODES.has(normalizeDetectorCode(event.code)));
}

function eventsForFamily(events: AnalysisEvidence[], family: ReadOnlyDetectorFamily) {
  return events.filter((event) => family.codes.includes(normalizeDetectorCode(event.code)));
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
  const [detectorEvidence, setDetectorEvidence] = useState<AnalysisEvidence[]>([]);
  const [localSelectedWeek, setLocalSelectedWeek] = useState<string | null>(null);
  const [error, setError] = useState("");
  const [detectorError, setDetectorError] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [isDetectorLoading, setIsDetectorLoading] = useState(false);

  useEffect(() => {
    let cancelled = false;
    const encodedSymbol = encodeURIComponent(symbol);
    setIsLoading(true);
    setIsDetectorLoading(true);
    setError("");
    setDetectorError("");
    setResponse(null);
    setDetectorEvidence([]);
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

    async function loadReadOnlyDetectorEvidence() {
      try {
        const payload = await fetchJson<AnalysisResponse>(
          `${API}/api/symbols/${encodedSymbol}/analysis`,
          "Read-only detector evidence failed",
        );
        if (!cancelled) {
          setDetectorEvidence(readOnlyDetectorEvidence(payload.evidence ?? []));
        }
      } catch (err) {
        if (!cancelled) {
          setDetectorError(err instanceof Error ? err.message : "Read-only detector evidence failed");
        }
      } finally {
        if (!cancelled) setIsDetectorLoading(false);
      }
    }

    void loadReadings();
    void loadReadOnlyDetectorEvidence();
    return () => {
      cancelled = true;
    };
  }, [symbol, lookback, onSelectWeek]);

  const readings = response?.readings ?? [];
  const selectedReading = useMemo(() => {
    const targetWeek = selectedWeek ?? localSelectedWeek;
    return readings.find((item) => item.week === targetWeek) ?? readings.at(-1) ?? null;
  }, [localSelectedWeek, readings, selectedWeek]);
  const selectedWeekDetectorEvidence = useMemo(() => {
    if (!selectedReading) return [];
    return detectorEvidence.filter((event) => event.week === selectedReading.week);
  }, [detectorEvidence, selectedReading]);

  function selectReading(item: WeeklyBarReading) {
    setLocalSelectedWeek(item.week);
    onSelectWeek?.(item.week);
  }

  function selectDetectorEvent(event: AnalysisEvidence) {
    setLocalSelectedWeek(event.week);
    onSelectWeek?.(event.week);
  }

  function renderSelectedWeekDetectorEvidence() {
    if (!selectedReading) return null;

    return (
      <div className={styles.selectedWeekDetectorEvidence}>
        <h4>Read-only Detector Evidence</h4>
        <small className={styles.selectedWeekDetectorGuardrail}>
          Selected-week detector evidence is review-only and does not change scoring, ranking, actionability, trade plan, alerts, or orders.
        </small>
        {isDetectorLoading && <small>Loading detector evidence for selected week...</small>}
        {!isDetectorLoading && detectorError && <small>Detector evidence unavailable: {detectorError}</small>}
        {!isDetectorLoading && !detectorError && selectedWeekDetectorEvidence.length === 0 && (
          <small>No Effort/Result or Absorption event in the current analysis response for this selected week.</small>
        )}
        {!isDetectorLoading && !detectorError && selectedWeekDetectorEvidence.length > 0 && (
          <ul className={styles.selectedWeekDetectorList}>
            {selectedWeekDetectorEvidence.map((event) => (
              <li className={styles.selectedWeekDetectorItem} key={`${event.week}-${event.bar_index}-${event.code}`}>
                <span className={styles.readOnlyDetectorBadge}>Read-only / not scoring</span>
                <strong>{detectorCodeLabel(event.code)}</strong>
                <p>{detectorReading(event)}</p>
                <small>{event.category} · {event.direction}</small>
              </li>
            ))}
          </ul>
        )}
      </div>
    );
  }

  function renderReadOnlyDetectorEvidence() {
    return (
      <section className={styles.readOnlyDetectorPanel}>
        <div className={styles.readOnlyDetectorHeading}>
          <div>
            <span className="section-kicker">READ-ONLY DETECTOR EVIDENCE</span>
            <h2>Effort / Result and Absorption</h2>
          </div>
          <span>{isDetectorLoading ? "Loading" : `${detectorEvidence.length} events`}</span>
        </div>
        <p className={styles.readOnlyDetectorGuardrail}>
          These backend detector families are production-visible for review only. They do not change the decision, ranking, actionability, trade plan, alerts, or orders.
        </p>
        {detectorError && <div className="status error-status">{detectorError}</div>}
        <div className={styles.readOnlyDetectorGrid}>
          {READ_ONLY_DETECTOR_FAMILIES.map((family) => {
            const familyEvents = eventsForFamily(detectorEvidence, family);
            const latestEvent = familyEvents.at(-1) ?? null;
            return (
              <button
                type="button"
                className={`${styles.readOnlyDetectorCard} ${latestEvent ? "" : styles.emptyDetectorCard}`}
                key={family.key}
                disabled={!latestEvent}
                onClick={() => {
                  if (latestEvent) selectDetectorEvent(latestEvent);
                }}
              >
                <span className={styles.readOnlyDetectorBadge}>Read-only / not scoring</span>
                <strong>{family.title}</strong>
                <p>{latestEvent ? detectorReading(latestEvent) : family.helper}</p>
                <small>
                  {latestEvent
                    ? `${detectorCodeLabel(latestEvent.code)} · latest ${displayDate(latestEvent.week)} · ${familyEvents.length} ${familyEvents.length === 1 ? "event" : "events"}`
                    : "No event in current analysis response"}
                </small>
              </button>
            );
          })}
        </div>
      </section>
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

      {renderReadOnlyDetectorEvidence()}
    </section>
  );
}
