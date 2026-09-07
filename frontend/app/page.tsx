"use client";

import { FormEvent, useEffect, useRef, useState } from "react";
import { ColorType, createChart, createSeriesMarkers } from "lightweight-charts";
import type { IChartApi, Time } from "lightweight-charts";
import { HLCSeries } from "./hlc-series";

type Bar = { bar_index: number; week: string; open: number; high: number; low: number; close: number; volume: number };
type Swing = { bar_index: number; confirmation_index: number; week: string; type: string; label: string | null; price: number; grade: string; is_failed: boolean; score: { overall: number; smart_money: number; professional: number } };
type Evidence = { code: string; category: string; direction: string; strength: number; quality: number; bar_index: number; week: string; observation: string; description: string };
type Analysis = { symbol: string; timeframe: string; latest_week: string; bars: Bar[]; trend: { direction: string; state: string; strength: number; confidence: number; swing_count: number }; structural_swings: Swing[]; evidence: Evidence[]; qualification: { qualification: string; actionable: boolean; reason: string }; professional: { net_strength: number; net_pressure: number; confidence: number } };

const API = process.env.NEXT_PUBLIC_API_URL ?? "http://127.0.0.1:8000";
const UP_COLOR = "#16a34a";
const DOWN_COLOR = "#dc2626";

function pretty(value: string) { return value.replaceAll("_", " ").replace(/\b\w/g, (char) => char.toUpperCase()); }

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
      return { time: Math.floor(new Date(bar.week).getTime() / 1000) as Time, high: bar.high, low: bar.low, close: bar.close, direction, structural: swing ? { label: swing.label ?? swing.type, price: swing.price, isHigh, color: isHigh ? DOWN_COLOR : UP_COLOR } : undefined };
    }));
    const evidenceMarkers = analysis.evidence.map((item) => {
      const bullish = item.direction.toLowerCase().includes("bull") || item.direction.toLowerCase().includes("demand");
      return { time: Math.floor(new Date(item.week).getTime() / 1000) as Time, position: bullish ? "belowBar" as const : "aboveBar" as const, shape: "circle" as const, color: bullish ? UP_COLOR : DOWN_COLOR, text: "" };
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
    const resize = () => { if (chartRef.current) chart.applyOptions({ width: chartRef.current.clientWidth, height: chartRef.current.clientHeight }); };
    window.addEventListener("resize", resize);
    return () => { window.removeEventListener("resize", resize); chart.remove(); chartApiRef.current = null; };
  }, [analysis]);

  function submit(event: FormEvent<HTMLFormElement>) { event.preventDefault(); const value = String(new FormData(event.currentTarget).get("symbol") ?? "").trim().toUpperCase(); if (value) setSymbol(value); }
  function fitChart() { chartApiRef.current?.timeScale().fitContent(); }
  function latestChart() { chartApiRef.current?.timeScale().scrollToRealTime(); }
  function zoomIn() { chartApiRef.current?.timeScale().zoomIn(); }
  function zoomOut() { chartApiRef.current?.timeScale().zoomOut(); }

  const latest = analysis?.bars.at(-1);
  const previous = analysis?.bars.at(-2);
  const change = latest && previous ? latest.close - previous.close : 0;
  const changePct = latest && previous && previous.close !== 0 ? (change / previous.close) * 100 : 0;
  const recentSwings = analysis?.structural_swings.slice(-8) ?? [];
  const latestSwing = analysis?.structural_swings.at(-1);
  const readSwing = selectedSwing ?? latestSwing;
  const readIsSelected = Boolean(selectedSwing);

  return (
    <main className="command-centre">
      <aside className="sidebar"><div className="brand">ProVSA<span>Command Centre</span></div><nav className="nav">{['Scanner', 'Watchlist', 'Signals', 'Charts', 'Reports', 'Market Overview', 'Data', 'Settings'].map((item) => <button className={item === 'Charts' ? 'active' : ''} key={item}>{item}</button>)}</nav></aside>
      <section className="workspace">
        <header className="header"><div className="symbol-title"><h1>{analysis?.symbol ?? symbol}</h1><span className="timeframe-badge">{analysis?.timeframe ?? "1W"}</span>{latest && <span className={change >= 0 ? "price-change up" : "price-change down"}>{latest.close.toFixed(2)} {change >= 0 ? "+" : ""}{change.toFixed(2)} ({changePct.toFixed(2)}%)</span>}</div><form className="symbol-form" onSubmit={submit}><input name="symbol" defaultValue={symbol} aria-label="Symbol" /><button type="submit">Analyze</button></form></header>
        <section className="chart-card"><div className="chart-header"><div className="layer-legend"><span className="chart-title">PRICE</span><span className="legend-item"><i className="legend-line price-line" />HLC</span><span className="legend-item"><i className="legend-dot structure-dot" />STRUCTURE</span><span className="legend-item"><i className="legend-dot evidence-dot" />VSA</span></div><div className="chart-tools"><button type="button" onClick={zoomOut} aria-label="Zoom out">−</button><button type="button" onClick={zoomIn} aria-label="Zoom in">+</button><button type="button" onClick={fitChart}>Fit</button><button type="button" onClick={latestChart}>Latest</button><span className="latest-date">{analysis?.latest_week ?? "Loading..."}</span></div></div>{error ? <div className="status">{error}</div> : <div className="chart-wrap" ref={chartRef} />}</section>
        {analysis && <>
          <div className="bottom-grid">
            <div className="panel trend"><h3>Trend</h3><strong>{pretty(analysis.trend.direction)}</strong><div className="panel-status">{pretty(analysis.trend.state)}</div><small>Strength {analysis.trend.strength.toFixed(2)} · Confidence {analysis.trend.confidence.toFixed(2)}</small></div>
            <div className="panel structure"><h3>Structure</h3><strong>{latestSwing?.label ?? "—"}</strong><div className="panel-status">{analysis.structural_swings.length} swings · {analysis.trend.swing_count} classified</div><small>Latest confirmed structural point</small></div>
            <div className="panel decision"><h3>Decision</h3><strong>{pretty(analysis.qualification.qualification)}</strong><div className="panel-status">{analysis.qualification.actionable ? "Actionable" : "Observation only"}</div><small>{analysis.qualification.reason}</small></div>
            <div className="panel professional"><h3>Professional Flow</h3><strong>{analysis.professional.net_strength.toFixed(2)}</strong><div className="panel-status">Pressure {analysis.professional.net_pressure.toFixed(2)}</div><small>Confidence {analysis.professional.confidence.toFixed(2)}</small></div>
          </div>
          <section className="structure-workspace">
            <div className="structure-sequence panel"><div className="workspace-heading"><div><span className="section-kicker">STRUCTURAL SEQUENCE</span><h2>Confirmed swing progression</h2></div><span>{recentSwings.length} latest points</span></div><div className="swing-track">{recentSwings.map((swing, index) => <button type="button" key={`${swing.bar_index}-${swing.type}`} className={`swing-node ${swing.type.toLowerCase().includes("high") ? "high" : "low"} ${selectedSwing?.bar_index === swing.bar_index ? "selected" : ""} ${latestSwing?.bar_index === swing.bar_index ? "latest" : ""}`} onClick={() => { setSelectedSwing(swing); setSelectedEvidence(null); }}><span>{swing.label ?? swing.type}</span><small>{swing.price.toFixed(0)}</small><em>{swing.grade}</em>{index < recentSwings.length - 1 && <b aria-hidden="true">→</b>}</button>)}</div></div>
            <div className="structure-summary panel"><span className="section-kicker">{readIsSelected ? "SELECTED STRUCTURE" : "LATEST STRUCTURE"}</span><h2>{readSwing?.label ?? "No confirmed swing"}</h2>{readSwing ? <><p>Confirmed {readSwing.type.toLowerCase()} at <strong>{readSwing.price.toFixed(2)}</strong>. {readSwing.is_failed ? "This structural point is marked failed." : "This structural point is confirmed."}</p><div className="summary-grid"><span>Grade<strong>{readSwing.grade}</strong></span><span>Overall<strong>{readSwing.score.overall.toFixed(2)}</strong></span><span>Smart Money<strong>{readSwing.score.smart_money.toFixed(2)}</strong></span></div></> : <p>No confirmed structural swing is available.</p>}</div>
          </section>
        </>}
      </section>
      <aside className="signals"><div className="signals-header"><div><span className="section-kicker">ANALYSIS</span><h2>VSA Evidence</h2></div><span className="signals-count">{analysis?.evidence.length ?? 0} observations</span></div>
        {selectedSwing && <div className="evidence-detail swing-detail"><div className="detail-title"><strong>{(selectedSwing.label ?? selectedSwing.type).toUpperCase()}</strong><button onClick={() => setSelectedSwing(null)}>×</button></div><div className="detail-meta">{selectedSwing.type} · bar {selectedSwing.bar_index} · confirmed {selectedSwing.confirmation_index}</div><div className="detail-metrics">Price {selectedSwing.price.toFixed(2)} · Grade {selectedSwing.grade}</div><div className="score-grid"><span>Overall<strong>{selectedSwing.score.overall.toFixed(2)}</strong></span><span>Smart Money<strong>{selectedSwing.score.smart_money.toFixed(2)}</strong></span><span>Professional<strong>{selectedSwing.score.professional.toFixed(2)}</strong></span></div><small>{selectedSwing.is_failed ? "Failed structural swing" : "Confirmed structural swing"}</small></div>}
        {selectedEvidence && <div className="evidence-detail"><div className="detail-title"><strong>{pretty(selectedEvidence.code)}</strong><button onClick={() => setSelectedEvidence(null)}>×</button></div><div className="detail-meta">{selectedEvidence.category} · {selectedEvidence.direction} · bar {selectedEvidence.bar_index}</div><div className="detail-metrics">Strength {selectedEvidence.strength.toFixed(2)} · Quality {selectedEvidence.quality.toFixed(2)}</div><p>{selectedEvidence.observation}</p><small>{selectedEvidence.description}</small></div>}
        <div className="history-heading">RECENT EVIDENCE</div>{analysis?.evidence.slice(-12).reverse().map((item) => { const bullish = item.direction.toLowerCase().includes("bull") || item.direction.toLowerCase().includes("demand"); return <button className="signal" key={`${item.bar_index}-${item.code}`} onClick={() => setSelectedEvidence(item)}><div className="signal-top"><span className={bullish ? "dot up" : "dot down"} /><strong>{pretty(item.code)}</strong><span>{item.strength.toFixed(2)}</span></div><div className="signal-code">{item.category} · {item.direction} · bar {item.bar_index}</div></button>; })}{!analysis && <div className="status">Loading analysis...</div>}
      </aside>
    </main>
  );
}
