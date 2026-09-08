export type DecisionJournalEvaluation = {
  entry_id: string;
  symbol: string;
  timeframe: string;
  outcome: string;
  checked_bars: number;
  first_checked_week: string | null;
  last_checked_week: string | null;
  confirmation_hit: boolean;
  invalidation_hit: boolean;
  favorable_move_pct: number | null;
  adverse_move_pct: number | null;
  notes: string;
};

export type DecisionJournalEvaluationResponse = {
  symbol: string;
  timeframe: string;
  horizon_bars: number;
  latest_week: string;
  persist_status: boolean;
  evaluations: DecisionJournalEvaluation[];
};

type DecisionJournalPanelProps = {
  response: DecisionJournalEvaluationResponse | null | undefined;
  error?: string;
  isLoading?: boolean;
};

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

function formatPercent(value: number | null) {
  return value === null ? "—" : `${value.toFixed(2)}%`;
}

function outcomeClass(outcome: string) {
  if (outcome === "confirmed") return "dot up";
  if (outcome === "invalidated" || outcome === "mixed") return "dot down";
  return "dot up";
}

function summarizeOutcomes(evaluations: DecisionJournalEvaluation[]) {
  return evaluations.reduce<Record<string, number>>((counts, item) => {
    counts[item.outcome] = (counts[item.outcome] ?? 0) + 1;
    return counts;
  }, {});
}

export function DecisionJournalPanel({
  response,
  error = "",
  isLoading = false,
}: DecisionJournalPanelProps) {
  const evaluations = response?.evaluations ?? [];
  const latest = evaluations.at(-1) ?? null;
  const outcomeCounts = summarizeOutcomes(evaluations);
  const recent = evaluations.slice(-6).reverse();

  return (
    <section className="structure-workspace">
      <div className="panel structure-summary">
        <span className="section-kicker">DECISION JOURNAL</span>
        <h2>{latest ? pretty(latest.outcome) : isLoading ? "Loading journal" : "No outcomes yet"}</h2>
        <p>
          {latest
            ? latest.notes
            : error || "Saved VSA Story expectations will appear here after analysis creates journal entries."}
        </p>
        <div className="summary-grid">
          <span>
            Entries
            <strong>{evaluations.length}</strong>
          </span>
          <span>
            Horizon
            <strong>{response ? `${response.horizon_bars} bars` : "—"}</strong>
          </span>
          <span>
            Latest Week
            <strong>{displayDate(response?.latest_week)}</strong>
          </span>
        </div>
        {latest && (
          <div className="plain-score">
            <span>Latest Move</span>
            <strong>{formatPercent(latest.favorable_move_pct)}</strong>
            <small>Adverse {formatPercent(latest.adverse_move_pct)}</small>
          </div>
        )}
      </div>

      <div className="panel structure-sequence">
        <div className="workspace-heading">
          <div>
            <span className="section-kicker">OUTCOME MIX</span>
            <h2>Expectation validation</h2>
          </div>
          <span>{response?.persist_status ? "Saved" : "Read-only"}</span>
        </div>
        {Object.keys(outcomeCounts).length === 0 ? (
          <p>{error || "No saved journal entries have been evaluated yet."}</p>
        ) : (
          <div className="vsa-category-list">
            {Object.entries(outcomeCounts).map(([outcome, count]) => (
              <span key={outcome}>
                {pretty(outcome)} · {count}
              </span>
            ))}
          </div>
        )}
      </div>

      <div className="panel structure-sequence">
        <div className="workspace-heading">
          <div>
            <span className="section-kicker">RECENT JOURNAL OUTCOMES</span>
            <h2>What happened after the story</h2>
          </div>
          <span>{recent.length} shown</span>
        </div>
        {recent.length === 0 ? (
          <p>{isLoading ? "Loading saved outcomes..." : "Run analysis over time to build validation history."}</p>
        ) : (
          recent.map((item) => (
            <div className="signal" key={item.entry_id}>
              <div className="signal-top">
                <span className={outcomeClass(item.outcome)} />
                <strong>{pretty(item.outcome)}</strong>
                <span>{item.checked_bars} bars</span>
              </div>
              <div className="signal-code">
                {displayDate(item.first_checked_week)} → {displayDate(item.last_checked_week)} · {item.confirmation_hit ? "confirmation hit" : "no confirmation"} · {item.invalidation_hit ? "invalidation hit" : "no invalidation"}
              </div>
              <p>{item.notes}</p>
              <small>
                Favorable {formatPercent(item.favorable_move_pct)} · Adverse {formatPercent(item.adverse_move_pct)}
              </small>
            </div>
          ))
        )}
      </div>
    </section>
  );
}
