"use client";

import { useEffect, useRef } from "react";
import {
  CandlestickSeries,
  ColorType,
  HistogramSeries,
  createChart,
  createSeriesMarkers,
  type SeriesMarker,
  type Time,
} from "lightweight-charts";

import type {
  ProgressionShadowReplayFrame,
  ProgressionShadowSemanticRole,
} from "./progression-shadow-replay-fixtures";

type ProgressionShadowReplayChartProps = {
  frames: ProgressionShadowReplayFrame[];
};

function replayTime(week: string): Time {
  return week.slice(0, 10) as Time;
}

function markerText(role: ProgressionShadowSemanticRole): string {
  return role
    .replaceAll("_", " ")
    .toLowerCase()
    .replace(/^./, (value) => value.toUpperCase());
}

function markerForFrame(
  frame: ProgressionShadowReplayFrame,
): SeriesMarker<Time> | null {
  if (!frame.is_event_bar || frame.semantic_role === null) {
    return null;
  }

  if (
    frame.semantic_role === "TRANSITION_WARNING" &&
    frame.projected_transition_direction === "bullish"
  ) {
    return {
      time: replayTime(frame.week),
      position: "belowBar",
      shape: "arrowUp",
      color: "#15803d",
      text: markerText(frame.semantic_role),
    };
  }

  if (
    frame.semantic_role === "TRANSITION_WARNING" &&
    frame.projected_transition_direction === "bearish"
  ) {
    return {
      time: replayTime(frame.week),
      position: "aboveBar",
      shape: "arrowDown",
      color: "#b91c1c",
      text: markerText(frame.semantic_role),
    };
  }

  return {
    time: replayTime(frame.week),
    position: "aboveBar",
    shape: "circle",
    color: "#475569",
    text: markerText(frame.semantic_role),
  };
}

export function ProgressionShadowReplayChart({
  frames,
}: ProgressionShadowReplayChartProps) {
  const containerRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    const container = containerRef.current;
    if (!container) {
      return;
    }

    const chart = createChart(container, {
      width: container.clientWidth,
      height: 430,
      layout: {
        background: {
          type: ColorType.Solid,
          color: "transparent",
        },
      },
      rightPriceScale: {
        borderVisible: false,
      },
      timeScale: {
        borderVisible: false,
        rightOffset: 1,
      },
      grid: {
        vertLines: {
          visible: false,
        },
      },
    });

    const candles = chart.addSeries(CandlestickSeries, {
      priceLineVisible: false,
      lastValueVisible: true,
    });
    candles.setData(
      frames.map((frame) => ({
        time: replayTime(frame.week),
        open: frame.open,
        high: frame.high,
        low: frame.low,
        close: frame.close,
      })),
    );

    const volume = chart.addSeries(HistogramSeries, {
      priceFormat: {
        type: "volume",
      },
      priceScaleId: "volume",
      priceLineVisible: false,
      lastValueVisible: false,
    });
    volume.setData(
      frames.map((frame) => ({
        time: replayTime(frame.week),
        value: frame.volume,
      })),
    );
    chart.priceScale("volume").applyOptions({
      scaleMargins: {
        top: 0.8,
        bottom: 0,
      },
    });

    const markers = frames
      .map(markerForFrame)
      .filter((item): item is SeriesMarker<Time> => item !== null);
    createSeriesMarkers(candles, markers);

    chart.timeScale().fitContent();

    const resize = new ResizeObserver(() => {
      chart.applyOptions({
        width: container.clientWidth,
      });
    });
    resize.observe(container);

    return () => {
      resize.disconnect();
      chart.remove();
    };
  }, [frames]);

  return (
    <div
      ref={containerRef}
      role="img"
      aria-label="Causal weekly candlestick replay chart"
      data-future-bars-allowed="false"
      data-live-api-fetch-allowed="false"
      data-production-effect="none"
      style={{
        width: "100%",
        minHeight: 430,
      }}
    />
  );
}
