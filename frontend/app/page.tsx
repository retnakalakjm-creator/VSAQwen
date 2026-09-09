"use client";

import { FormEvent, useEffect, useRef, useState } from "react";
import { ColorType, createChart, createSeriesMarkers } from "lightweight-charts";
import type { IChartApi, Time } from "lightweight-charts";
import { DataSourceStatusPanel } from "./data-source-status-panel";
import { DecisionContextPanel } from "./decision-context-panel";
import type { DecisionContext, DecisionContextEvent } from "./decision-context-panel";
import { DecisionJournalPanel } from "./decision-journal-panel";
import type { DecisionJournalEvaluation, DecisionJournalEvaluationResponse } from "./decision-journal-panel";
import { HLCSeries } from "./hlc-series";

type Bar = { bar_index: number; week: string; open: number; high: number; low: number; close: number; volume: number };
type Swing = { bar_index: number; confirmation_index: number; week: string; type: string; label: string | null; price: number; grade: string; is_failed: boolean; score: { overall: number; smart_money: number; professional: number } };
type Evidence = { code: string; category: string; direction: string; strength: number; quality: number; bar_index: number; week: string; observation: string; description: string };
type Analysis = { symbol: string; timeframe: string; latest_week: string; bars: Bar[]; trend: { direction: string; state: string; strength: number; confidence: number; swing_count: number }; structural_swings: Swing[]; evidence: Evidence[]; qualification: { qualification: string; actionable: boolean; reason: string }; professional: { net_strength: number; net_pressure: number; confidence: number }; decision_context?: DecisionContext | null };
type WorkspaceSection = "overview" | "chart" | "story" | "evidence" | "structure" | "journal" | "data";

type WorkspaceMeta = { key: WorkspaceSection; label: string; helper: string };
type EvidenceCategorySummary = { category: string; count: number; latestWeek: string | null };
type ProfessionalSummaryRow = { label: string; value: string; detail: string };

const API = process.env.NEXT_PUBLIC_API_URL ?? "http://127.0.0.1:8000";
const UP_COLOR = "#16a34a";
const DOWN_COLOR = "#dc2626";
const WORKSPACE_SECTIONS: WorkspaceMeta[] = [
  { key: "overview", label: "Dashboard", helper: "Verdict + chart" },
  { key: "chart", label: "Chart", helper: "Price + structure" },
  { key: "story", label: "VSA Story", helper: "Confirmed/developing" },
  { key: "evidence", label: "Bar-by-Bar", helper: "Professional reading" },
  { key: "structure", label: "Structure", helper: "Swing sequence" },
  { key: "journal", label: "Journal", helper: "Expectation validation" },
  { key: "data", label: "Diagnostics", helper: "Source/cache" },
];

function pretty(value: string | null | undefined) {
  return value ? value.replaceAll("_", " ").replace(/\b\w/g, (char) => char.toUpperCase()) : "—";
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

function plainConfidence(value: number | null | undefined) {
  if (value === null || value === undefined || Number.isNaN(value)) return "Confidence is not available yet.";
  if (value >= 0.85) return "The evidence is highly aligned and the story is unusually clear.";
  if (value >= 0.70) return "The evidence is well aligned and the story is clear.";
  if (value >= 0.55) return "The evidence is constructive, but still needs confirmation.";
  if (value >= 0.40) return "The evidence is mixed; treat the story as conditional.";
  if (value >= 0.20) return "The model has limited conviction in this reading.";
  return "The model has very low conviction in this reading.";
}

function directionWord(direction: string) {
  return direction.toLowerCase().includes("bull") || direction.toLowerCase().includes("demand") ? "bullish" : "bearish";
}

function displayDate(value: string | undefined | null) {
  if (!value) return "—";
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? value : date.toLocaleDateString("en-IN", { day: "2-digit", month: "short", year: "numeric" });
}

function chartTime(value: string | undefined | null): Time {
  const date = value ? new Date(value) : new Date();
  if (!Number.isNaN(date.getTime())) date.setUTCDate(date.getUTCDate() + 1);
  return Math.floor(date.getTime() / 1000) as Time;
}

function evidenceTone(event: Evidence) {
  const category = event.category.toLowerCase();
  const direction = event.direction.toLowerCase();
  if (category.includes("demand") || direction.includes("demand") || direction.includes("bull")) return "Demand evidence";
  if (category.includes("supply") || direction.includes("supply") || direction.includes("bear")) return "Supply evidence";
  if (category.includes("effort")) return "Effort evidence";
  return "Context evidence";
}

function professionalReading(event: Evidence) {
  return event.observation || event.description || "Professional reading is not available for this bar yet.";
}

function pressurePhrase(value: number | null | undefined) {
  if (value === null || value === undefined || Number.isNaN(value)) return "Pressure is not available yet.";
  if (value >= 0.55) return "Demand is clearly in control.";
  if (value >= 0.20) return "Demand is stronger than supply.";
  if (value > -0.20) return "Supply and demand are mixed.";
  if (value > -0.55) return "Supply is stronger than demand.";
  return "Supply is clearly in control.";
}

function professionalActivityPhrase(value: number | null | undefined) {
  if (value === null || value === undefined || Number.isNaN(value)) return "Professional activity is not available yet.";
  if (value >= 0.70) return "Active professional buying/support is visible.";
  if (value >= 0.45) return "Professional support is present but not aggressive.";
  if (value >= 0.20) return "Professional participation is light.";
  if (value > -0.20) return "Professional activity is neutral or unclear.";
  if (value > -0.55) return "Professional selling/supply is present.";
  return "Strong professional selling/supply is visible.";
}

function supplyPhrase(analysis: Analysis | null, context: DecisionContext | null | undefined) {
  if (!analysis) return "Unknown";
  const pressure = analysis.professional.net_pressure;
  const hasRecentSupply = analysis.evidence.slice(-8).some((item) => item.category.toLowerCase().includes("supply") || item.direction.toLowerCase().includes("supply"));
  if (pressure >= 0.35 && hasRecentSupply) return "Present but being absorbed";
  if (pressure >= 0.20) return "Drying up";
  if (pressure > -0.20) return "Mixed";
  if (context?.bias?.toLowerCase().includes("bull")) return "Needs monitoring";
  return "Increasing";
}

function demandPhrase(analysis: Analysis | null) {
  if (!analysis) return "Unknown";
  const pressure = analysis.professional.net_pressure;
  if (pressure >= 0.55) return "Strong and active";
  if (pressure >= 0.20) return "Increasing";
  if (pressure > -0.20) return "Mixed";
  if (pressure > -0.55) return "Weakening";
  return "Weak";
}

function backgroundPhrase(context: DecisionContext | null | undefined) {
  const phase = (context?.phase ?? "").toLowerCase();
  const bias = (context?.bias ?? "").toLowerCase();
  if (phase.includes("accumulation")) return "Professional accumulation";
  if (phase.includes("distribution")) return "Professional distribution";
  if (bias.includes("bull")) return "Constructive bullish background";
  if (bias.includes("bear")) return "Weak bearish background";
  return "Developing VSA background";
}

function suggestedPosture(context: DecisionContext | null | undefined, analysis: Analysis | null) {
  const decision = pretty(context?.decision ?? context?.tradability ?? analysis?.qualification.qualification);
  if (!decision || decision === "—") return "Wait for confirmed context";
  return decision;
}

function riskPhrase(context: DecisionContext | null | undefined, analysis: Analysis | null) {
  const confidence = context?.confidence ?? analysis?.professional.confidence;
  const tradability = (context?.tradability ?? analysis?.qualification.qualification ?? "").toLowerCase();
  if (tradability.includes("wait") || tradability.includes("observe")) return "Controlled only after confirmation";
  if ((confidence ?? 0) >= 0.70) return "Lower, but not risk-free";
  if ((confidence ?? 0) >= 0.45) return "Moderate";
  return "Elevated";
}

function rewardPhrase(context: DecisionContext | null | undefined, analysis: Analysis | null) {
  const confidence = context?.confidence ?? analysis?.professional.confidence;
  const bias = (context?.bias ?? "").toLowerCase();
  if ((confidence ?? 0) >= 0.70 && bias.includes("bull")) return "High if confirmation appears";
  if ((confidence ?? 0) >= 0.45) return "Moderate and conditional";
  return "Unclear until structure improves";
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

export default function Home() {
  const chartRef = useRef<HTMLDivElement>(null);
  const chartApiRef = useRef<IChartApi | null>(null);
  const [symbol, setSymbol] = useState("SRF.NS");
  const [analysis, setAnalysis] = useState<Analysis | null>(null);
  const [decisionContextPreview, setDecisionContextPreview] = useState<DecisionContext | null>(null);
  const [journalResponse, setJournalResponse] = useState<DecisionJournalEvaluationResponse | null>(null);
  const [journalError, setJournalError] = useState("");
  const [journalLoading, setJournalLoading] = useState(false);
  const [selectedJournalEntryId, setSelectedJournalEntryId] = useState("");
  const [selectedEvidence, setSelectedEvidence] = useState<Evidence | null>(null);
  const [selectedSwing, setSelectedSwing] = useState<Swing | null>(null);
  const [activeSection, setActiveSection] = useState<WorkspaceSection>("overview");
  const [error, setError] = useState("");

  useEffect(() => {
    let cancelled = false;
    const encodedSymbol = encodeURIComponent(symbol);
    setSelectedEvidence(null);
    setSelectedSwing(null);
    setSelectedJournalEntryId("");
    setAnalysis(null);
    setDecisionContextPreview(null);
    setJournalResponse(null);
    setJournalError("");
    setJournalLoading(true);
    setError("");

    async function loadJournal() {
      try {
        const journal = await fetchJson<DecisionJournalEvaluationResponse>(
          `${API}/api/symbols/${encodedSymbol}/decision-journal/evaluations`,
          "Decision journal failed",
        );
        if (!cancelled) {
          setJournalResponse(journal);
          setJournalError("");
        }
      } catch (err) {
        if (!cancelled) {
          setJournalResponse(null);
          setJournalError(err instanceof Error ? err.message : "Decision journal failed");
        }
      } finally {
        if (!cancelled) setJournalLoading(false);
      }
    }

    async function loadSymbol() {
      void loadJournal();
      try {
        const preview = await fetchJson<DecisionContext>(`${API}/api/symbols/${encodedSymbol}/decision-context`, "Decision context failed");
        if (!cancelled) setDecisionContextPreview(preview);
      } catch {
        if (!cancelled) setDecisionContextPreview(null);
      }
      try {
        const data = await fetchJson<Analysis>(`${API}/api/symbols/${encodedSymbol}/analysis`, "Analysis failed");
        if (!cancelled) {
          setAnalysis(data);
          setDecisionContextPreview(data.decision_context ?? null);
          setError("");
        }
        void loadJournal();
      } catch (err) {
        if (!cancelled) setError(err instanceof Error ? err.message : "Analysis failed");
      }
    }

    void loadSymbol();
    return () => { cancelled = true; };
  }, [symbol]);

  const shouldShowChart = activeSection === "overview" || activeSection === "chart" || activeSection === "evidence";
  const decisionContext = analysis?.decision_context ?? decisionContextPreview;
  const latest = analysis?.bars.at(-1);
  const previous = analysis?.bars.at(-2);
  const change = latest && previous ? latest.close - previous.close : 0;
  const changePct = latest && previous && previous.close !== 0 ? (change / previous.close) * 100 : 0;
  const recentSwings = analysis?.structural_swings.slice(-8) ?? [];
  const latestSwing = analysis?.structural_swings.at(-1);
  const readSwing = selectedSwing ?? latestSwing;
  const readIsSelected = Boolean(selectedSwing);
  const displayedEvidence = selectedEvidence ?? analysis?.evidence.at(-1) ?? null;
  const recentEvidence = analysis?.evidence.slice(-12) ?? [];
  const activeSectionMeta = WORKSPACE_SECTIONS.find((item) => item.key === activeSection) ?? WORKSPACE_SECTIONS[0];
  const eventMix = buildEventMix(recentEvidence);

  useEffect(() => {
    if (!chartRef.current || !analysis || !shouldShowChart) return;

    const chart: IChartApi = createChart(chartRef.current, {
      layout: { background: { type: ColorType.Solid, color: "#ffffff" }, textColor: "#334155" },
      grid: { vertLines: { color: "#eef2f7" }, horzLines: { color: "#eef2f7" } },
      rightPriceScale: { borderColor: "#cbd5e1", scaleMargins: { top: 0.14, bottom: 0.10 } },
      timeScale: { borderColor: "#cbd5e1", timeVisible: false, rightOffset: 5, barSpacing: 9 },
      crosshair: { vertLine: { color: "#94a3b8", width: 1 }, horzLine: { color: "#94a3b8", width: 1 } },
      width: chartRef.current.clientWidth,
      height: chartRef.current.clientHeight,
    });
    chartApiRef.current = chart;

    const structuralByBar = new Map(analysis.structural_swings.map((swing) => [swing.bar_index, swing]));
    const series = chart.addCustomSeries(new HLCSeries(), { lineWidth: 2, tickLength: 5 });
    series.setData(analysis.bars.map((bar, index) => {
      const swing = structuralByBar.get(bar.bar_index);
      const isHigh = swing ? swing.type.toLowerCase().includes("high") : false;
      const direction: "up" | "down" | "flat" = index === 0 ? "flat" : bar.close > analysis.bars[index - 1].close ? "up" : bar.close < analysis.bars[index - 1].close ? "down" : "flat";
      return {
        time: chartTime(bar.week),
        high: bar.high,
        low: bar.low,
        close: bar.close,
        direction,
        highlight: selectedEvidence?.bar_index === bar.bar_index || selectedSwing?.bar_index === bar.bar_index,
        structural: swing ? { label: swing.label ?? swing.type, price: swing.price, isHigh, color: isHigh ? DOWN_COLOR : UP_COLOR } : undefined,
      };
    }));

    const evidenceMarkers = analysis.evidence.map((item) => {
      const bullish = item.direction.toLowerCase().includes("bull") || item.direction.toLowerCase().includes("demand");
      const selected = selectedEvidence?.bar_index === item.bar_index && selectedEvidence?.code === item.code;
      return {
        time: chartTime(item.week),
        position: bullish ? "belowBar" as const : "aboveBar" as const,
        shape: "circle" as const,
        color: selected ? "#2563eb" : bullish ? UP_COLOR : DOWN_COLOR,
        text: "",
      };
    });
    createSeriesMarkers(series, evidenceMarkers);

    chart.subscribeClick((param) => {
      if (!param.time) return;
      const time = Number(param.time);
      const evidence = analysis.evidence.filter((item) => Number(chartTime(item.week)) === time);
      const swings = analysis.structural_swings.filter((item) => Number(chartTime(item.week)) === time);
      if (evidence.length) {
        setSelectedEvidence(evidence[evidence.length - 1]);
        setSelectedSwing(null);
      }
      if (swings.length) {
        setSelectedSwing(swings[swings.length - 1]);
        setSelectedEvidence(null);
      }
    });

    chart.timeScale().fitContent();
    const selectedBarIndex = selectedEvidence?.bar_index ?? selectedSwing?.bar_index;
    if (selectedBarIndex !== undefined) {
      const from = Math.max(0, selectedBarIndex - 28);
      const to = Math.min(analysis.bars.length + 3, selectedBarIndex + 14);
      chart.timeScale().setVisibleLogicalRange({ from, to });
    }

    const resize = () => {
      if (chartRef.current) chart.applyOptions({ width: chartRef.current.clientWidth, height: chartRef.current.clientHeight });
    };
    window.addEventListener("resize", resize);
    return () => {
      window.removeEventListener("resize", resize);
      chart.remove();
      chartApiRef.current = null;
    };
  }, [analysis, selectedEvidence?.bar_index, selectedEvidence?.code, selectedSwing?.bar_index, activeSection, shouldShowChart]);

  function buildEventMix(events: Evidence[]): EvidenceCategorySummary[] {
    const summaries = new Map<string, EvidenceCategorySummary>();
    events.forEach((item) => {
      const category = pretty(item.category);
      const summary = summaries.get(category) ?? { category, count: 0, latestWeek: null };
      summary.count += 1;
      summary.latestWeek = item.week;
      summaries.set(category, summary);
    });
    return Array.from(summaries.values()).sort((a, b) => b.count - a.count || a.category.localeCompare(b.category));
  }

  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const value = String(new FormData(event.currentTarget).get("symbol") ?? "").trim().toUpperCase();
    if (value) setSymbol(value);
  }

  function fitChart() { chartApiRef.current?.timeScale().fitContent(); }
  function latestChart() { chartApiRef.current?.timeScale().scrollToRealTime(); }
  function zoomTimeScale(multiplier: number) {
    const timeScale = chartApiRef.current?.timeScale();
    if (!timeScale) return;
    const range = timeScale.getVisibleLogicalRange();
    if (!range) { timeScale.fitContent(); return; }
    const from = Number(range.from);
    const to = Number(range.to);
    const center = (from + to) / 2;
    const halfWidth = Math.max(4, ((to - from) * multiplier) / 2);
    timeScale.setVisibleLogicalRange({ from: center - halfWidth, to: center + halfWidth });
  }
  function zoomIn() { zoomTimeScale(0.72); }
  function zoomOut() { zoomTimeScale(1.35); }

  function evidenceDate(item: Evidence) { return analysis?.bars.find((bar) => bar.bar_index === item.bar_index)?.week ?? item.week; }
  function confirmationDate(swing: Swing) { return analysis?.bars.find((bar) => bar.bar_index === swing.confirmation_index)?.week ?? swing.week; }

  function selectDecisionContextEvent(event: DecisionContextEvent) {
    const exactEvidence = analysis?.evidence.find((item) => item.bar_index === event.bar_index && item.code === event.code);
    const sameBarEvidence = analysis?.evidence.find((item) => item.bar_index === event.bar_index);
    const sameBarSwing = analysis?.structural_swings.find((item) => item.bar_index === event.bar_index || item.confirmation_index === event.bar_index);
    if (exactEvidence || sameBarEvidence) {
      setSelectedEvidence(exactEvidence ?? sameBarEvidence ?? null);
      setSelectedSwing(null);
      setActiveSection("evidence");
      return;
    }
    if (sameBarSwing) {
      setSelectedSwing(sameBarSwing);
      setSelectedEvidence(null);
      setActiveSection("structure");
    }
  }

  function selectBarContext(barIndex: number | null | undefined) {
    if (barIndex === null || barIndex === undefined) return false;
    const exactEvidence = analysis?.evidence.find((item) => item.bar_index === barIndex);
    if (exactEvidence) {
      setSelectedEvidence(exactEvidence);
      setSelectedSwing(null);
      setActiveSection("evidence");
      return true;
    }
    const sameBarSwing = analysis?.structural_swings.find((item) => item.bar_index === barIndex || item.confirmation_index === barIndex);
    if (sameBarSwing) {
      setSelectedSwing(sameBarSwing);
      setSelectedEvidence(null);
      setActiveSection("structure");
      return true;
    }
    const storyEvent = decisionContext?.recent_events.find((item) => item.bar_index === barIndex);
    if (storyEvent) { selectDecisionContextEvent(storyEvent); return true; }
    return false;
  }

  function selectJournalEvaluation(evaluation: DecisionJournalEvaluation) {
    setSelectedJournalEntryId(evaluation.entry_id);
    if (selectBarContext(evaluation.source_context_bar_index)) return;
    const firstCheckedBar = analysis?.bars.find((bar) => bar.week === evaluation.first_checked_week);
    if (firstCheckedBar) selectBarContext(firstCheckedBar.bar_index);
  }

  function professionalRows(): ProfessionalSummaryRow[] {
    return [
      { label: "Trend", value: analysis ? `${scoreLevel(analysis.trend.strength)} ${pretty(analysis.trend.direction)}` : "Loading", detail: analysis ? `The broader weekly trend is ${pretty(analysis.trend.state).toLowerCase()}.` : "Waiting for analysis." },
      { label: "Background", value: backgroundPhrase(decisionContext), detail: "Interpreted from the confirmed VSA story and current phase." },
      { label: "Current phase", value: pretty(decisionContext?.phase), detail: decisionContext?.story.summary ?? "Phase appears after confirmed context is available." },
      { label: "Supply", value: supplyPhrase(analysis, decisionContext), detail: "Supply wording is an interpretation of recent pressure, not a standalone bearish signal." },
      { label: "Demand", value: demandPhrase(analysis), detail: pressurePhrase(analysis?.professional.net_pressure) },
      { label: "Professional activity", value: professionalActivityPhrase(analysis?.professional.net_strength).replace(/\.$/, ""), detail: "Converted from model strength into trader-readable wording." },
      { label: "Risk", value: riskPhrase(decisionContext, analysis), detail: "Risk remains conditional until confirmation and invalidation levels are respected." },
      { label: "Reward potential", value: rewardPhrase(decisionContext, analysis), detail: "Exact swing targets require the dedicated trade-planning layer planned after this UI refactor." },
      { label: "Suggested posture", value: suggestedPosture(decisionContext, analysis), detail: "This is decision-support posture, not order placement or broker action." },
      { label: "Confidence", value: scoreLevel(decisionContext?.confidence ?? analysis?.professional.confidence), detail: plainConfidence(decisionContext?.confidence ?? analysis?.professional.confidence) },
    ];
  }

  function renderProfessionalSummary() {
    return (
      <section className="panel professional-summary-card">
        <div className="workspace-heading professional-summary-heading">
          <div><span className="section-kicker">PROFESSIONAL SUMMARY</span><h2>{decisionContext?.story.headline ?? "Building confirmed weekly verdict"}</h2></div>
          <span>{decisionContext ? "Confirmed weekly" : "Loading"}</span>
        </div>
        <div className="professional-summary-grid">
          {professionalRows().map((row) => <div className="professional-summary-row" key={row.label}><span>{row.label}</span><strong>{row.value}</strong><small>{row.detail}</small></div>)}
        </div>
        <p className="professional-summary-note">Trade entries such as buy-on-pullback, breakout entry, target range, and stop/invalidation mapping will be produced by a dedicated trade-planning layer after this UI refactor. This screen stays decision-support only.</p>
      </section>
    );
  }

  function renderChartPanel() {
    return (
      <section className="chart-card readable-chart-card">
        <div className="chart-header">
          <div className="layer-legend"><span className="chart-title">PRICE</span><span className="legend-item"><i className="legend-line price-line" />HLC</span><span className="legend-item"><i className="legend-dot structure-dot" />STRUCTURE</span><span className="legend-item"><i className="legend-dot evidence-dot" />VSA</span></div>
          <div className="chart-tools"><button type="button" onClick={zoomOut} aria-label="Zoom out">−</button><button type="button" onClick={zoomIn} aria-label="Zoom in">+</button><button type="button" onClick={fitChart}>Fit</button><button type="button" onClick={latestChart}>Latest</button><span className="latest-date">{analysis?.latest_week || decisionContext?.latest_week ? displayDate(analysis?.latest_week ?? decisionContext?.latest_week) : "Loading..."}</span></div>
        </div>
        {error ? <div className="status">{error}</div> : shouldShowChart ? <div className="chart-wrap" ref={chartRef} /> : null}
      </section>
    );
  }

  function renderSummaryCards() {
    if (!analysis) return <div className="status readable-status">Loading real-market analysis...</div>;
    return (
      <div className="bottom-grid readable-bottom-grid">
        <button type="button" className="panel trend readable-summary-card" onClick={() => setActiveSection("chart")}><h3>Trend</h3><strong>{`${scoreLevel(analysis.trend.strength)} ${pretty(analysis.trend.direction)}`}</strong><div className="panel-status">{pretty(analysis.trend.state)}</div><small>{plainConfidence(analysis.trend.confidence)}</small></button>
        <button type="button" className="panel structure readable-summary-card" onClick={() => setActiveSection("structure")}><h3>Structure</h3><strong>{latestSwing?.label ?? "—"}</strong><div className="panel-status">{analysis.structural_swings.length} swings · {analysis.trend.swing_count} classified</div><small>Open swing progression separately for details.</small></button>
        <button type="button" className="panel decision readable-summary-card" onClick={() => setActiveSection("story")}><h3>Decision</h3><strong>{suggestedPosture(decisionContext, analysis)}</strong><div className="panel-status">{decisionContext ? `${pretty(decisionContext.phase)} · ${pretty(decisionContext.bias)}` : analysis.qualification.actionable ? "Actionable" : "Observation only"}</div><small>{decisionContext?.story.headline ?? analysis.qualification.reason}</small></button>
        <button type="button" className="panel professional readable-summary-card" onClick={() => setActiveSection("evidence")}><h3>Professional Flow</h3><strong>{professionalActivityPhrase(analysis.professional.net_strength).replace(/\.$/, "")}</strong><div className="panel-status">{pressurePhrase(analysis.professional.net_pressure)}</div><small>{plainConfidence(analysis.professional.confidence)}</small></button>
      </div>
    );
  }

  function renderSelectedDetail() {
    if (selectedSwing) {
      return <div className="evidence-detail swing-detail readable-detail-reset"><div className="detail-title"><strong>{(selectedSwing.label ?? selectedSwing.type).toUpperCase()}</strong><button type="button" onClick={() => setSelectedSwing(null)}>×</button></div><div className="detail-meta">Structural point · observed {displayDate(selectedSwing.week)} · confirmed {displayDate(confirmationDate(selectedSwing))}</div><p>Confirmed {selectedSwing.type.toLowerCase()} at {selectedSwing.price.toFixed(2)}. {selectedSwing.is_failed ? "This structural point is marked failed." : "This structural point remains valid."}</p><small>Internal model grades are hidden from the main reading. Use this as structural context, not an order signal.</small></div>;
    }
    if (selectedEvidence) {
      return <div className="evidence-detail readable-detail-reset professional-reading-detail"><div className="detail-title"><strong>Week Ending {displayDate(evidenceDate(selectedEvidence))}</strong><button type="button" onClick={() => setSelectedEvidence(null)}>×</button></div><h4>Professional Reading</h4><p>{professionalReading(selectedEvidence)}</p>{selectedEvidence.description && <small>{selectedEvidence.description}</small>}</div>;
    }
    if (displayedEvidence) {
      return <div className="evidence-detail latest-evidence readable-detail-reset professional-reading-detail"><h3>Week Ending {displayDate(evidenceDate(displayedEvidence))}</h3><h4>Professional Reading</h4><p>{professionalReading(displayedEvidence)}</p><small>Select any week to inspect its professional reading.</small></div>;
    }
    return <p>Select a week or chart marker to inspect the professional reading here.</p>;
  }

  function renderEvidenceComposition() {
    return (
      <div className="panel evidence-composition-card">
        <div className="workspace-heading"><div><span className="section-kicker">RECENT EVIDENCE COMPOSITION</span><h2>Detected VSA categories</h2></div><span>{recentEvidence.length} events</span></div>
        <p className="composition-note">This is a category legend/count only. Seeing Supply here does not mean the final market bias is bearish. The Professional Summary combines demand, supply, effort, trend, and structure into the final interpretation.</p>
        <div className="evidence-composition-list">
          {eventMix.length === 0 ? <span>No recent events yet.</span> : eventMix.map((item) => <button key={item.category} type="button" onClick={() => setSelectedEvidence(recentEvidence.slice().reverse().find((event) => pretty(event.category) === item.category) ?? null)}><strong>{item.category}</strong><span>{item.count} {item.count === 1 ? "event" : "events"}</span><small>Latest {displayDate(item.latestWeek)}</small></button>)}
        </div>
      </div>
    );
  }

  function renderEvidencePanel() {
    return (
      <section className="readable-two-column">
        <div className="readable-stack">
          {renderChartPanel()}
          {renderEvidenceComposition()}
          <div className="panel bar-story-card">
            <div className="workspace-heading"><div><span className="section-kicker">BAR-BY-BAR INTERPRETATION</span><h2>Recent weekly professional reading</h2></div><span>{recentEvidence.length} shown</span></div>
            <p className="composition-note">This view follows the uploaded reference format: Week Ending plus Professional Reading. It is a narrative reading of the recent weekly bars, not a trade-plan or order instruction.</p>
            {recentEvidence.slice().reverse().map((item) => (
              <button type="button" className={`bar-reading-card ${selectedEvidence?.bar_index === item.bar_index && selectedEvidence?.code === item.code ? "selected" : ""}`} key={`${item.bar_index}-${item.code}`} onClick={() => { setSelectedEvidence(item); setSelectedSwing(null); }}>
                <span>Week Ending</span>
                <strong>{displayDate(evidenceDate(item))}</strong>
                <h3>Professional Reading</h3>
                <p>{professionalReading(item)}</p>
              </button>
            ))}
            {!analysis && <div className="status">Loading analysis...</div>}
          </div>
        </div>
        <aside className="panel readable-detail-panel"><span className="section-kicker">SELECTED WEEK</span>{renderSelectedDetail()}</aside>
      </section>
    );
  }

  function renderStructurePanel() {
    if (!analysis) return <div className="status readable-status">Loading structure...</div>;
    return (
      <section className="structure-workspace readable-structure-section">
        <div className="structure-sequence panel"><div className="workspace-heading"><div><span className="section-kicker">STRUCTURAL SEQUENCE</span><h2>Confirmed swing progression</h2></div><span>{recentSwings.length} latest points</span></div><div className="swing-track">{recentSwings.map((swing, index) => <button type="button" key={`${swing.bar_index}-${swing.type}`} className={`swing-node ${swing.type.toLowerCase().includes("high") ? "high" : "low"} ${selectedSwing?.bar_index === swing.bar_index ? "selected" : ""} ${latestSwing?.bar_index === swing.bar_index ? "latest" : ""}`} onClick={() => { setSelectedSwing(swing); setSelectedEvidence(null); }}><span>{swing.label ?? swing.type}</span><small>{swing.price.toFixed(0)}</small><em>{swing.grade}</em>{latestSwing?.bar_index === swing.bar_index && <i>LATEST</i>}{index < recentSwings.length - 1 && <b aria-hidden="true">→</b>}</button>)}</div></div>
        <div className="structure-summary panel"><span className="section-kicker">{readIsSelected ? "SELECTED STRUCTURE" : "LATEST STRUCTURE"}</span><h2>{readSwing?.label ?? "No confirmed swing"}</h2>{readSwing ? <><p>Confirmed {readSwing.type.toLowerCase()} at <strong>{readSwing.price.toFixed(2)}</strong>. {readSwing.is_failed ? "This structural point is marked failed." : "This structural point is confirmed."}</p><div className="summary-grid readable-summary-grid"><span>Grade<strong>{readSwing.grade}</strong></span><span>Overall<strong>{scoreLevel(readSwing.score.overall)}</strong><small>Evidence strength in plain English.</small></span><span>Smart Money<strong>{scoreLevel(readSwing.score.smart_money)}</strong><small>Smart-money alignment in plain English.</small></span></div></> : <p>No confirmed structural swing is available.</p>}</div>
      </section>
    );
  }

  function renderOverviewPanel() {
    return (
      <section className="readable-stack">
        {renderProfessionalSummary()}
        {renderChartPanel()}
        {renderSummaryCards()}
        <div className="readable-overview-grid">
          <div className="panel readable-story-preview"><span className="section-kicker">PRIMARY STORY</span><h2>{decisionContext?.story.headline ?? "Loading confirmed story"}</h2><p>{decisionContext?.story.summary ?? "The confirmed weekly decision context will appear here after analysis."}</p><button type="button" className="readable-link-button" onClick={() => setActiveSection("story")}>Open VSA Story</button></div>
          <div className="panel readable-data-preview"><span className="section-kicker">LOW PRIORITY DIAGNOSTICS</span><h2>Data source and cache freshness</h2><p>Provider/cache details are available separately so they do not compete with the trading story.</p><button type="button" className="readable-link-button secondary" onClick={() => setActiveSection("data")}>Open Diagnostics</button></div>
        </div>
      </section>
    );
  }

  function renderActiveSection() {
    if (activeSection === "chart") return <section className="readable-stack">{renderChartPanel()}{renderSummaryCards()}</section>;
    if (activeSection === "story") return <DecisionContextPanel context={decisionContext} onSelectEvent={selectDecisionContextEvent} />;
    if (activeSection === "evidence") return renderEvidencePanel();
    if (activeSection === "structure") return renderStructurePanel();
    if (activeSection === "journal") return <DecisionJournalPanel response={journalResponse} error={journalError} isLoading={journalLoading} selectedEntryId={selectedJournalEntryId} onSelectEvaluation={selectJournalEvaluation} />;
    if (activeSection === "data") return <DataSourceStatusPanel symbol={analysis?.symbol ?? decisionContext?.symbol ?? symbol} />;
    return renderOverviewPanel();
  }

  return (
    <main className="command-centre readable-shell">
      <aside className="sidebar readable-sidebar"><div className="brand">ProVSA<span>Command Centre</span></div><nav className="nav readable-nav" aria-label="Main workspace sections">{WORKSPACE_SECTIONS.map((item) => <button className={item.key === activeSection ? "active" : ""} key={item.key} onClick={() => setActiveSection(item.key)} type="button"><strong>{item.label}</strong><span>{item.helper}</span></button>)}</nav></aside>
      <section className="workspace readable-workspace">
        <header className="header readable-header"><div className="symbol-title"><h1>{analysis?.symbol ?? decisionContext?.symbol ?? symbol}</h1><span className="timeframe-badge">{analysis?.timeframe ?? decisionContext?.timeframe ?? "1W"}</span>{latest && <span className={change >= 0 ? "price-change up" : "price-change down"}>{latest.close.toFixed(2)} {change >= 0 ? "+" : ""}{change.toFixed(2)} ({changePct.toFixed(2)}%)</span>}</div><form className="symbol-form" onSubmit={submit}><input name="symbol" defaultValue={symbol} aria-label="Symbol" /><button type="submit">Analyze</button></form></header>
        <section className="readable-page-title"><div><span className="section-kicker">{activeSectionMeta.helper}</span><h2>{activeSectionMeta.label}</h2></div><p>{activeSection === "data" ? "Diagnostics only. No market-data download, scanner refresh, order, account, holding, fund, margin, or position action is triggered from this view." : "Trader-readable workspace. Internal scores are converted into plain-English interpretation."}</p></section>
        <div className="readable-tabbar" role="tablist" aria-label="Workspace sections">{WORKSPACE_SECTIONS.map((item) => <button key={item.key} type="button" className={item.key === activeSection ? "selected" : ""} aria-pressed={item.key === activeSection} onClick={() => setActiveSection(item.key)}>{item.label}</button>)}</div>
        {renderActiveSection()}
      </section>
    </main>
  );
}
