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

  const latestEvents = context.recent_events.slice().reverse().slice(0, 6);
  const latestSwings = context.structural_swings.slice(-4);
  const positivePressure = context.net_pressure >= 0;

  return (
    <section className="structure-workspace">
      <div className="panel structure-summary">
        <span className="section-kicker">VSA STORY</span>
        <h2>{context.story.headline}</h2>
        <p>{context.story.summary}</p>
        <div className="summary-grid">
          <span>
            Phase
            <strong>{pretty(context.phase)}</strong>
          </span>
          <span>
            Tradability
            <strong>{pretty(context.tradability)}</strong>
          </span>
          <span>
            Bias
            <strong>{pretty(context.bias)}</strong>
          </span>
        </div>
        <div className="plain-score">
          <span>Pressure</span>
          <strong>{positivePressure ? "Demand" : "Supply"}</strong>
          <small>{score(context.net_pressure)} net pressure</small>
        </div>
        <div className="plain-score">
          <span>Confidence</span>
          <strong>{score(context.confidence)}</strong>
          <small>Evaluated {displayDate(context.evaluated_at_utc)}</small>
        </div>
      </div>

      <div className="panel structure-sequence">
        <div className="workspace-heading">
          <div>
            <span className="section-kicker">WHAT TO WATCH NEXT</span>
            <h2>Confirmation and invalidation</h2>
          </div>
          <span>{pretty(context.mode)}</span>
        </div>
        <div className="evidence-detail latest-evidence">
          <h4>Confirmation</h4>
          <p>{context.story.confirmation_condition}</p>
          <h4>Invalidation</h4>
          <p>{context.story.invalidation_condition}</p>
        </div>
        <div className="vsa-category-summary">
          <span className="section-kicker">EXPECTED NEXT BEHAVIOR</span>
          <div className="vsa-category-list">
            {context.story.what_to_expect_next.map((item) => (
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
