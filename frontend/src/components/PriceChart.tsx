import { useEffect, useRef } from "react";
import { createChart, ColorType, IChartApi } from "lightweight-charts";
import type { Candle } from "../api/types";

// Candlestick price chart with an optional OI / volume histogram overlay.
export function PriceChart({
  candles,
  oiSeries,
  height = 360,
}: {
  candles: Candle[];
  oiSeries?: { time: string; value: number }[];
  height?: number;
}) {
  const ref = useRef<HTMLDivElement>(null);
  const chartRef = useRef<IChartApi | null>(null);

  useEffect(() => {
    if (!ref.current) return;
    const chart = createChart(ref.current, {
      height,
      layout: {
        background: { type: ColorType.Solid, color: "#FCFBF8" },
        textColor: "#5C564C",
        fontFamily: "ui-monospace, monospace",
      },
      grid: {
        vertLines: { color: "#E3DBCB" },
        horzLines: { color: "#E3DBCB" },
      },
      rightPriceScale: { borderColor: "#E3DBCB" },
      timeScale: { borderColor: "#E3DBCB", timeVisible: true },
      crosshair: { mode: 0 },
    });
    chartRef.current = chart;

    const candleSeries = chart.addCandlestickSeries({
      upColor: "#15803D",
      downColor: "#C0392B",
      borderUpColor: "#15803D",
      borderDownColor: "#C0392B",
      wickUpColor: "#15803D",
      wickDownColor: "#C0392B",
    });

    const toTime = (iso: string) => {
      const d = new Date(iso);
      return Math.floor(d.getTime() / 1000) as any;
    };

    candleSeries.setData(
      candles.map((c) => ({
        time: toTime(c.time),
        open: c.open,
        high: c.high,
        low: c.low,
        close: c.close,
      }))
    );

    if (oiSeries && oiSeries.length) {
      const oi = chart.addHistogramSeries({
        priceScaleId: "oi",
        color: "#BE5A3A",
        priceFormat: { type: "volume" },
      });
      chart.priceScale("oi").applyOptions({
        scaleMargins: { top: 0.8, bottom: 0 },
      });
      oi.setData(oiSeries.map((p) => ({ time: toTime(p.time), value: p.value })));
    }

    chart.timeScale().fitContent();

    const ro = new ResizeObserver(() => {
      if (ref.current) chart.applyOptions({ width: ref.current.clientWidth });
    });
    ro.observe(ref.current);

    return () => {
      ro.disconnect();
      chart.remove();
    };
  }, [candles, oiSeries, height]);

  return <div ref={ref} className="w-full" />;
}
