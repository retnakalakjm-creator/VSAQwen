import { BitmapCoordinatesRenderingScope, CanvasRenderingTarget2D } from "fancy-canvas";
import {
  CustomData,
  CustomSeriesOptions,
  CustomSeriesPricePlotValues,
  ICustomSeriesPaneRenderer,
  ICustomSeriesPaneView,
  PaneRendererCustomData,
  PriceToCoordinateConverter,
  Time,
  WhitespaceData,
  customSeriesDefaultOptions,
} from "lightweight-charts";

export interface HLCData extends CustomData<Time> {
  high: number;
  low: number;
  close: number;
  direction: "up" | "down" | "flat";
  highlight?: boolean;
  structural?: { label: string; price: number; isHigh: boolean; color: string };
}

export interface HLCSeriesOptions extends CustomSeriesOptions {
  lineWidth: number;
  tickLength: number;
}

const defaultOptions: HLCSeriesOptions = {
  ...customSeriesDefaultOptions,
  lineWidth: 2,
  tickLength: 5,
};

const UP_COLOR = "#16a34a";
const DOWN_COLOR = "#dc2626";
const FLAT_COLOR = "#64748b";
const HIGHLIGHT_COLOR = "#2563eb";

class HLCSeriesRenderer implements ICustomSeriesPaneRenderer {
  private data: PaneRendererCustomData<Time, HLCData> | null = null;
  private options: HLCSeriesOptions | null = null;

  update(data: PaneRendererCustomData<Time, HLCData>, options: HLCSeriesOptions): void {
    this.data = data;
    this.options = options;
  }

  draw(target: CanvasRenderingTarget2D, priceConverter: PriceToCoordinateConverter): void {
    target.useBitmapCoordinateSpace((scope) => this.drawImpl(scope, priceConverter));
  }

  private drawImpl(scope: BitmapCoordinatesRenderingScope, priceConverter: PriceToCoordinateConverter): void {
    if (!this.data || !this.options || !this.data.visibleRange) return;

    const { bars, visibleRange, barSpacing } = this.data;
    const { context, horizontalPixelRatio, verticalPixelRatio } = scope;
    const lineWidth = Math.max(2, Math.round(this.options.lineWidth * verticalPixelRatio));
    const tickLength = Math.min(this.options.tickLength, Math.max(4, barSpacing * 0.35)) * horizontalPixelRatio;

    context.lineWidth = lineWidth;
    context.lineCap = "square";
    context.globalAlpha = 1;

    for (let index = visibleRange.from; index < visibleRange.to; index += 1) {
      const bar = bars[index];
      if (!bar || !Number.isFinite(bar.x)) continue;

      const high = priceConverter(bar.originalData.high);
      const low = priceConverter(bar.originalData.low);
      const close = priceConverter(bar.originalData.close);
      if (high === null || low === null || close === null) continue;

      const x = Math.round(bar.x * horizontalPixelRatio) + 0.5;
      const highY = high * verticalPixelRatio;
      const lowY = low * verticalPixelRatio;
      const closeY = close * verticalPixelRatio;

      context.lineWidth = lineWidth;
      context.strokeStyle = bar.originalData.highlight
        ? HIGHLIGHT_COLOR
        : bar.originalData.direction === "up"
          ? UP_COLOR
          : bar.originalData.direction === "down"
            ? DOWN_COLOR
            : FLAT_COLOR;
      context.beginPath();
      context.moveTo(x, highY);
      context.lineTo(x, lowY);
      context.moveTo(x, closeY);
      context.lineTo(x + tickLength, closeY);
      context.stroke();

      const structural = bar.originalData.structural;
      if (!structural) continue;

      const swingY = priceConverter(structural.price);
      if (swingY === null) continue;

      const direction = structural.isHigh ? -1 : 1;
      const triangleSize = Math.max(5, Math.min(7, barSpacing * 0.24)) * horizontalPixelRatio;
      const triangleY = swingY * verticalPixelRatio + direction * 13 * verticalPixelRatio;
      const labelY = triangleY + direction * 8 * verticalPixelRatio;

      context.fillStyle = structural.color;
      context.beginPath();
      context.moveTo(x, triangleY + direction * triangleSize);
      context.lineTo(x - triangleSize, triangleY - direction * triangleSize * 0.65);
      context.lineTo(x + triangleSize, triangleY - direction * triangleSize * 0.65);
      context.closePath();
      context.fill();

      context.font = `700 ${Math.max(11, Math.min(14, barSpacing * 0.48)) * verticalPixelRatio}px Arial, sans-serif`;
      context.textAlign = "center";
      context.textBaseline = structural.isHigh ? "bottom" : "top";
      context.fillStyle = structural.color;
      context.fillText(structural.label.toUpperCase(), x, labelY);
    }
  }
}

export class HLCSeries implements ICustomSeriesPaneView<Time, HLCData, HLCSeriesOptions> {
  private rendererInstance = new HLCSeriesRenderer();

  priceValueBuilder(plotRow: HLCData): CustomSeriesPricePlotValues {
    return [plotRow.low, plotRow.high, plotRow.close];
  }

  isWhitespace(data: HLCData | WhitespaceData): data is WhitespaceData {
    return (data as Partial<HLCData>).close === undefined;
  }

  renderer(): HLCSeriesRenderer {
    return this.rendererInstance;
  }

  update(data: PaneRendererCustomData<Time, HLCData>, options: HLCSeriesOptions): void {
    this.rendererInstance.update(data, options);
  }

  defaultOptions(): HLCSeriesOptions {
    return defaultOptions;
  }
}
