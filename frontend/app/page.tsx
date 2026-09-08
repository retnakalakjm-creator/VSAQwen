"use client";

import { FormEvent, useEffect, useRef, useState } from "react";
import { ColorType, createChart, createSeriesMarkers } from "lightweight-charts";
import type { IChartApi, Time } from "lightweight-charts";
import { DecisionContextPanel } from "./decision-context-panel";
import type { DecisionContext, DecisionContextEvent } from "./decision-context-panel";
import { HLCSeries } from "./hlc-series";

type Bar = { bar_index: number; week: string; open: number; high: number; low: number; close: number; volume: number };
type Swing = { bar_index: number; confirmation_index: number; week: string; type: string; label: string | null; price: number; grade: string; is_failed: boolean; score: { overall: number; smart_money: number; professional: number } };
type Evidence = { code: string; category: string; direction: string; strength: number; quality: number; bar_index: number; week: string; observation: string; description: string };
type Analysis = { symbol: string; timeframe: string; latest_week: string; bars: Bar[]; trend: { direction: string; state: string; strength: number; confidence: number; swing_count: number }; structural_swings: Swing[]; evidence: Evidence[]; qualification: { qualification: string; actionable: boolean; reason: string }; professional: { net_strength: number; net_pressure: number; confidence: number }; decision_context?: DecisionContext | null };

const API = process.env.NEXT_PUBLIC_API_URL ?? "http://127.0.0.1:8000";
const UP_COLOR = "#16a34a";
const DOWN_COLOR = "#dc2626";

function pretty(value: string) { return value.replaceAll("_", " ").replace(/\b\w/g, (char) => char.toUpperCase()); }
function scoreLevel(value: number) { if (value >= 0.75) return "Very strong"; if (value >= 0.60) return "Strong"; if (value >= 0.45) return "Moderate"; if (value >= 0.25) return "Weak"; return "Very weak"; }
function scoreMeaning(value: number, subject: string) { return `${scoreLevel(value)} ${subject.toLowerCase()} according to the model.`; }
function directionWord(direction: string) { return direction.toLowerCase().includes("bull") || direction.toLowerCase().includes("demand") ? "bullish" : "bearish"; }
function displayDate(value: string | undefined) {
  if (!value) return "—";
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? value : date.toLocaleDateString("en-IN", { day: "2-digit", month: "short", year: "numeric" });
}

export default function Home() {
  const chartRef = useRef<HTMLDivElement>(null);
  const chartApiRef = useRef<IChartApi | null>(null);
  const [symbol, setSymbol] = useState("SRF.NS");
  const [analysis, setAnalysis] = useState<Analysis | null>(null);
  const [selectedEvidence, setSelectedEvidence] = useState<Evidence | null>(null);
  const [selectedSwing, setSelectedSwing] = useState<Swing | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    let cancelled = false;
    setSelectedEvidence(null); setSelectedSwing(null);
    fetch(`${API}/api/symbols/${encodeURIComponent(symbol)}/analysis`)
      .then((response) => response.ok ? response.json() : response.json().then((body) => Promise.reject(new Error(body.detail ?? "Analysis failed"))))
      .then((data: Analysis) => { if (!cancelled) { setAnalysis(data); setError(""); } })
      .catch((err: Error) => { if (!cancelled) setError(err.message); });
    return () => { cancelled = true; };
  }, [symbol]);

  useEffect(() => {
    if (!chartRef.current || !analysis) return;
    const chart: IChartApi = createChart(chartRef.current, {
      layout: { background: { type: ColorType.Solid, color: "#ffffff" }, textColor: "#334155" },
      grid: { vertLines: { color: "#eef2f7" }, horzLines: { color: "#eef2f7" } },
      rightPriceScale: { borderColor: "#cbd5e1", scaleMargins: { top: 0.14, bottom: 0.10 } },
      timeScale: { borderColor: "#cbd5e1", timeVisible: false, rightOffset: 5, barSpacing: 9 },
      crosshair: { vertLine: { color: "#94a3b8", width: 1 }, horzLine: { color: "#94a3b8", width: 1 } },
      width: chartRef.current.clientWidth, height: chartRef.current.clientHeight,
    });
    chartApiRef.current = chart;
    const structuralByBar = new Map(analysis.structural_swings.map((swing) => [swing.bar_index, swing]));
    const series = chart.addCustomSeries(new HLCSeries(), { lineWidth: 2, tickLength: 5 });
    series.setData(analysis.bars.map((bar, index) => {
      const swing = structuralByBar.get(bar.bar_index);
      const isHigh = swing ? swing.type.toLowerCase().includes("high") : false;
      const direction: "up" | "down" | "flat" = index === 0 ? "flat" : bar.close > analysis.bars[index - 1].close ? "up" : bar.close < analysis.bars[index - 1].close ? "down" : "flat";
      return {
        time: Math.floor(new Date(bar.week).getTime() / 1000) as Time,
        high: bar.high,
        low: bar.low,
        close: bar.close,
        direction,
        highlight: selectedEvidence?.bar_index === bar.bar_index,
        structural: swing ? { label: swing.label ?? swing.type, price: swing.price, isHigh, color: isHigh ? DOWN_COLOR : UP_COLOR } : undefined,
      };
    }));
    const evidenceMarkers = analysis.evidence.map((item) => {
      const bullish = item.direction.toLowerCase().includes("bull") || item.direction.toLowerCase().includes("demand");
      const selected = selectedEvidence?.bar_index === item.bar_index && selectedEvidence?.code === item.code;
      return { time: Math.floor(new Date(item.week).getTime() / 1000) as Time, position: bullish ? "belowBar" as const : "aboveBar" as const, shape: "circle" as const, color: selected ? "#2563eb" : bullish ? UP_COLOR : DOWN_COLOR, text: "" };
    });
    createSeriesMarkers(series, evidenceMarkers);
    chart.subscribeClick((param) => {
      if (!param.time) return;
      const time = Number(param.time);
      const evidence = analysis.evidence.filter((item) => Math.floor(new Date(item.week).getTime() / 1000) === time);
      const swings = analysis.structural_swings.filter((item) => Math.floor(new Date(item.week).getTime() / 1000) === time);
      if (evidence.length) setSelectedEvidence(evidence[evidence.length - 1]);
      if (swings.length) setSelectedSwing(swings[swings.length - 1]);
    });
    chart.timeScale().fitContent();
    if (selectedEvidence) {
      const from = Math.max(0, selectedEvidence.bar_index - 28);
      const to = Math.min(analysis.bars.length + 3, selectedEvidence.bar_index + 14);
      chart.timeScale().setVisibleLogicalRange({ from, to });
    }
    const resize = () => { if (chartRef.current) chart.applyOptions({ width: chartRef.current.clientWidth, height: chartRef.current.clientHeight }); };
    window.addEventListener("resize", resize);
    return () => { window.removeEventListener("resize", resize); chart.remove(); chartApiRef.current = null; };
  }, [analysis, selectedEvidence?.bar_index, selectedEvidence?.code]);

  function submit(event: FormEvent<HTMLFormElement>) { event.preventDefault(); const value = String(new FormData(event.currentTarget).get("symbol") ?? "").trim().toUpperCase(); if (value) setSymbol(value); }
  function fitChart() { chartApiRef.current?.timeScale().fitContent(); }
  function latestChart() { chartApiRef.current?.timeScale().scrollToRealTime(); }
  function zoomTimeScale(multiplier: number) {
    const timeScale = chartApiRef.current?.timeScale();
    if (!timeScale) return;
    const range = timeScale.getVisibleLogicalRange();
    if (!range) {
      timeScale.fitContent();
      return;
    }
    const from = Number(range.from);
    const to = Number(range.to);
    const center = (from + to) / 2;
    const halfWidth = Math.max(4, ((to - from) * multiplier) / 2);
    timeScale.setVisibleLogicalRange({ from: center - halfWidth, to: center + halfWidth });
  }
  function zoomIn() { zoomTimeScale(0.72); }
  function zoomOut() { zoomTimeScale(1.35); }

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
  const evidenceCategories = Array.from(new Set(recentEvidence.map((item) => item.category)));
  const decisionContext = analysis?.decision_context ?? null;

  function evidenceDate(item: Evidence) {
    return analysis?.bars.find((bar) => bar.bar_index === item.bar_index)?.week ?? item.week;
  }
  function confirmationDate(swing: Swing) {
    return analysis?.bars.find((bar) => bar.bar_index === swing.confirmation_index)?.week ?? swing.week;
  }
  function selectDecisionContextEvent(event: DecisionContextEvent) {
    const exactEvidence = analysis?.evidence.find((item) => item.bar_index === event.bar_index && item.code === event.code);
    const sameBarEvidence = analysis?.evidence.find((item) => item.bar_index === event.bar_index);
    const sameBarSwing = analysis?.structural_swings.find((item) => item.bar_index === event.bar_index || item.confirmation_index === event.bar_index);
    if (exactEvidence || sameBarEvidence) {
      setSelectedEvidence(exactEvidence ?? sameBarEvidence ?? null);
      setSelectedSwing(null);
      return;
    }
    if (sameBarSwing) {
      setSelectedSwing(sameBarSwing);
      setSelectedEvidence(null);
    }
  }

  return (
    <main className="command-centre">
      <aside className="sidebar"><div className="brand">ProVSA<span>Command Centre</span></div><nav className="nav">{['Scanner', 'Watchlist', 'Signals', 'Charts', 'Reports', 'Market Overview', 'Data', 'Settings'].map((item) => <button className={item === 'Charts' ? 'active' : ''} key={item}>{item}</button>)}</nav></aside>
      <section className="workspace">
        <header className="header"><div className="symbol-title"><h1>{analysis?.symbol ?? symbol}</h1><span className="timeframe-badge">{analysis?.timeframe ?? "1W"}</span>{latest && <span className={change >= 0 ? "price-change up" : "price-change down"}>{latest.close.toFixed(2)} {change >= 0 ? "+" : ""}{change.toFixed(2)} ({changePct.toFixed(2)}%)</span>}</div><form className="symbol-form" onSubmit={submit}><input name="symbol" defaultValue={symbol} aria-label="Symbol" /><button type="submit">Analyze</button></form></header>
        <section className="chart-card"><div className="chart-header"><div className="layer-legend"><span className="chart-title">PRICE</span><span className="legend-item"><i className="legend-line price-line" />HLC</span><span className="legend-item"><i className="legend-dot structure-dot" />STRUCTURE</span><span className="legend-item"><i className="legend-dot evidence-dot" />VSA</span></div><div className="chart-tools"><button type="button" onClick={zoomOut} aria-label="Zoom out">−</button><button type="button" onClick={zoomIn} aria-label="Zoom in">+</button><button type="button" onClick={fitChart}>Fit</button><button type="button" onClick={latestChart}>Latest</button><span className="latest-date">{analysis?.latest_week ? displayDate(analysis.latest_week) : "Loading..."}</span></div></div>{error ? <div className="status">{error}</div> : <div className="chart-wrap" ref={chartRef} />}</section>
        {analysis && <>
          <div className="bottom-grid">
            <div className="panel trend"><h3>Trend</h3><strong>{pretty(analysis.trend.direction)}</strong><div className="panel-status">{pretty(analysis.trend.state)}</div><small>Strength {scoreLevel(analysis.trend.strength)} · Confidence {scoreLevel(analysis.trend.confidence)}</small></div>
            <div className="panel structure"><h3>Structure</h3><strong>{latestSwing?.label ?? "—"}</strong><div className="panel-status">{analysis.structural_swings.length} swings · {analysis.trend.swing_count} classified</div><small>Latest confirmed structural point</small></div>
            <div className="panel decision"><h3>Decision</h3><strong>{pretty(decisionContext?.tradability ?? analysis.qualification.qualification)}</strong><div className="panel-status">{decisionContext ? `${pretty(decisionContext.phase)} · ${pretty(decisionContext.bias)}` : analysis.qualification.actionable ? "Actionable" : "Observation only"}</div><small>{decisionContext?.story.headline ?? analysis.qualification.reason}</small></div>
            <div className="panel professional"><h3>Professional Flow</h3><strong>{scoreLevel(analysis.professional.net_strength)}</strong><div className="panel-status">{decisionContext ? `${pretty(decisionContext.bias)} bias` : analysis.professional.net_strength >= 0 ? "Positive" : "Negative"}</div><small>{scoreMeaning(analysis.professional.confidence, "confidence")}</small></div>
          </div>
          <DecisionContextPanel context={decisionContext} onSelectEvent={selectDecisionContextEvent} />
          <section className="structure-workspace">
            <div className="structure-sequence panel"><div className="workspace-heading"><div><span className="section-kicker">STRUCTURAL SEQUENCE</span><h2>Confirmed swing progression</h2></div><span>{recentSwings.length} latest points</span></div><div className="swing-track">{recentSwings.map((swing, index) => <button type="button" key={`${swing.bar_index}-${swing.type}`} className={`swing-node ${swing.type.toLowerCase().includes("high") ? "high" : "low"} ${selectedSwing?.bar_index === swing.bar_index ? "selected" : ""} ${latestSwing?.bar_index === swing.bar_index ? "latest" : ""}`} onClick={() => { setSelectedSwing(swing); setSelectedEvidence(null); }}><span>{swing.label ?? swing.type}</span><small>{swing.price.toFixed(0)}</small><em>{swing.grade}</em>{latestSwing?.bar_index === swing.bar_index && <i>LATEST</i>}{index < recentSwings.length - 1 && <b aria-hidden="true">→</b>}</button>)}</div></div>
            <div className="structure-summary panel"><span className="section-kicker">{readIsSelected ? "SELECTED STRUCTURE" : "LATEST STRUCTURE"}</span><h2>{readSwing?.label ?? "No confirmed swing"}</h2>{readSwing ? <><p>Confirmed {readSwing.type.toLowerCase()} at <strong>{readSwing.price.toFixed(2)}</strong>. {readSwing.is_failed ? "This structural point is marked failed." : "This structural point is confirmed."}</p><div className="summary-grid"><span>Grade<strong>{readSwing.grade}</strong></span><span>Overall<strong>{readSwing.score.overall.toFixed(2)}</strong><small>{scoreMeaning(readSwing.score.overall, "overall evidence strength")}</small></span><span>Smart Money<strong>{readSwing.score.smart_money.toFixed(2)}</strong><small>{scoreMeaning(readSwing.score.smart_money, "Smart Money alignment")}</small></span></div></> : <p>No confirmed structural swing is available.</p>}</div>
          </section>
        </>}
      </section>
      <aside className="signals"><div className="signals-header"><div><span className="section-kicker">ANALYSIS</span><h2>VSA Evidence</h2></div><span className="signals-count">{analysis?.evidence.length ?? 0} observations</span></div>
        {selectedSwing && <div className="evidence-detail swing-detail"><div className="detail-title"><strong>{(selectedSwing.label ?? selectedSwing.type).toUpperCase()}</strong><button onClick={() => setSelectedSwing(null)}>×</button></div><div className="detail-meta">Structural point · observed {displayDate(selectedSwing.week)} · confirmed {displayDate(confirmationDate(selectedSwing))}</div><div className="detail-metrics">Price {selectedSwing.price.toFixed(2)} · Grade {selectedSwing.grade}</div><div className="score-grid"><span>Overall<strong>{selectedSwing.score.overall.toFixed(2)}</strong><small>{scoreMeaning(selectedSwing.score.overall, "overall evidence strength")}</small></span><span>Smart Money<strong>{selectedSwing.score.smart_money.toFixed(2)}</strong><small>{scoreMeaning(selectedSwing.score.smart_money, "Smart Money alignment")}</small></span><span>Professional<strong>{selectedSwing.score.professional.toFixed(2)}</strong><small>{scoreMeaning(selectedSwing.score.professional, "professional participation")}</small></span></div><small>{selectedSwing.is_failed ? "Failed structural swing" : "Confirmed structural swing"}</small></div>}
        {selectedEvidence && <div className="evidence-detail"><div className="detail-title"><strong>{pretty(selectedEvidence.code)}</strong><button onClick={() => setSelectedEvidence(null)}>×</button></div><div className="detail-meta">{selectedEvidence.category} · {directionWord(selectedEvidence.direction)} · observed {displayDate(evidenceDate(selectedEvidence))}</div><div className="detail-metrics">Observed bar {selectedEvidence.bar_index} · VSA strength: {scoreLevel(selectedEvidence.strength)} · Evidence quality: {scoreLevel(selectedEvidence.quality)}</div><h4>What the evidence says</h4><p>{selectedEvidence.observation}</p><small>{selectedEvidence.description}</small></div>}
        {!selectedEvidence && displayedEvidence && <div className="evidence-detail latest-evidence"><span className="section-kicker">LATEST VSA OBSERVATION</span><h3>{pretty(displayedEvidence.code)}</h3><div className="detail-meta">{displayedEvidence.category} · {directionWord(displayedEvidence.direction)} · observed {displayDate(evidenceDate(displayedEvidence))}</div><h4>What the evidence says</h4><p>{displayedEvidence.observation}</p><div className="plain-score"><span>Strength</span><strong>{scoreLevel(displayedEvidence.strength)}</strong><small>{displayedEvidence.strength.toFixed(2)} model score</small></div></div>}
        {analysis && recentEvidence.length > 0 && <div className="vsa-category-summary"><span className="section-kicker">EVENT MIX</span><div className="vsa-category-list">{evidenceCategories.map((category) => <span key={category}>{pretty(category)}</span>)}</div></div>}
        <div className="history-heading">VSA EVENT TIMELINE</div>{recentEvidence.slice().reverse().map((item) => { const bullish = item.direction.toLowerCase().includes("bull") || item.direction.toLowerCase().includes("demand"); return <button type="button" className={`signal ${selectedEvidence?.bar_index === item.bar_index && selectedEvidence?.code === item.code ? "selected" : ""}`} key={`${item.bar_index}-${item.code}`} onClick={() => { setSelectedEvidence(item); setSelectedSwing(null); }}><div className="signal-top"><span className={bullish ? "dot up" : "dot down"} /><strong>{pretty(item.code)}</strong><span>{scoreLevel(item.strength)}</span></div><div className="signal-code">{displayDate(evidenceDate(item))} · {item.category} · {directionWord(item.direction)}</div><p>{item.observation}</p></button>; })}{!analysis && <div className="status">Loading analysis...</div>}
      </aside>
    </main>
  );
}
