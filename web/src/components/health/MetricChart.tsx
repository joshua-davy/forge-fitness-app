import { useState } from "react";
import { Area, AreaChart, CartesianGrid, Line, ResponsiveContainer, Tooltip, XAxis, YAxis, ReferenceLine } from "recharts";
import type { MetricSeries } from "@/types";
import { api } from "@/lib/api";
import { useEffect } from "react";
import "./MetricChart.css";

const RANGES = ["7d", "30d", "90d", "6m", "1y", "all"] as const;

interface Props {
  metric: string;
  label: string;
  color?: string;
  unit?: string;
  date?: string | null;
}

export function MetricChart({ metric, label, color = "#6BE3A4", unit = "", date }: Props) {
  const [range, setRange] = useState<string>("30d");
  const [data, setData] = useState<MetricSeries | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setLoading(true); setError(null);
    api.metricSeries(metric, range, date)
      .then(setData)
      .catch((e: Error) => setError(e.message))
      .finally(() => setLoading(false));
  }, [metric, range, date]);

  const series = data?.series ?? [];
  const movingAverage = data?.moving_avg_7d ?? [];
  const flags = data?.flags ?? [];
  const insights = data?.insights ?? [];
  const correlations = data?.correlations ?? [];
  const chartRows = series.map((point) => ({
    ...point,
    avg7: movingAverage.find((avg) => avg.date === point.date)?.value ?? null,
  })) ?? [];
  const resolvedUnit = data?.unit ?? unit;
  const comparison = data?.comparison?.delta_pct;

  return (
    <div className="mchart">
      <div className="mchart__head">
        <div>
          <div className="mchart__label">{data?.label ?? label}</div>
          {data?.coverage && (
            <div className={`mchart__coverage ${data.coverage.coverage_pct < 65 ? "mchart__coverage--low" : ""}`}>
              {data.coverage.covered_days} / {data.coverage.expected_days} days covered
            </div>
          )}
        </div>
        <div className="mchart__ranges">
          {RANGES.map(r => (
            <button key={r} className={`mchart__range ${range === r ? "mchart__range--on" : ""}`} onClick={() => setRange(r)}>
              {r.toUpperCase()}
            </button>
          ))}
        </div>
      </div>

      {data?.stats && (
        <div className="mchart__stats">
          <span>Latest <strong>{fmt(data.stats.latest)}{resolvedUnit}</strong></span>
          <span>Avg <strong>{fmt(data.stats.avg)}{resolvedUnit}</strong></span>
          <span>Min <strong>{fmt(data.stats.min)}{resolvedUnit}</strong></span>
          <span>Max <strong>{fmt(data.stats.max)}{resolvedUnit}</strong></span>
          <span>Trend <strong>{(data.stats.trend ?? "tracked").replace("_", " ")}</strong></span>
          {comparison !== null && comparison !== undefined && (
            <span className={comparison >= 0 ? "mchart__up" : "mchart__down"}>
              Vs prev <strong>{comparison > 0 ? "+" : ""}{comparison}%</strong>
            </span>
          )}
        </div>
      )}

      <div className="mchart__area">
        {loading && <div className="mchart__loader">Loading…</div>}
        {error && <div className="mchart__error">{error}</div>}
        {!loading && !error && data && series.length === 0 && (
          <div className="mchart__empty">No data for this range</div>
        )}
        {!loading && !error && data && series.length > 0 && (
          <ResponsiveContainer width="100%" height={230}>
            <AreaChart data={chartRows} margin={{ top: 8, right: 10, bottom: 0, left: -10 }}>
              <defs>
                <linearGradient id={`grad-${metric}`} x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor={color} stopOpacity={0.3} />
                  <stop offset="100%" stopColor={color} stopOpacity={0.0} />
                </linearGradient>
              </defs>
              <CartesianGrid stroke="rgba(255,255,255,0.04)" strokeDasharray="3 3" />
              <XAxis dataKey="date" tick={{ fontSize: 10, fill: "#76746E", fontFamily: "JetBrains Mono" }}
                tickFormatter={(d) => d.slice(5)} interval="preserveStartEnd" />
              <YAxis tick={{ fontSize: 10, fill: "#76746E", fontFamily: "JetBrains Mono" }} width={36} />
              {data.stats.avg && (
                <ReferenceLine y={data.stats.avg} stroke="rgba(255,255,255,0.12)" strokeDasharray="4 4" />
              )}
              <Tooltip
                contentStyle={{ background: "#08090C", border: "1px solid rgba(255,255,255,0.08)", borderRadius: 10, fontFamily: "JetBrains Mono", fontSize: 12 }}
                labelStyle={{ color: "#B8B6B0" }}
                itemStyle={{ color }}
                formatter={(v: unknown, name: unknown) => [`${v}${resolvedUnit}`, name === "avg7" ? "7-day avg" : label]}
              />
              <Area type="monotone" dataKey="value" stroke={color} strokeWidth={2}
                fill={`url(#grad-${metric})`} dot={false} activeDot={{ r: 4, fill: color }} />
              <Line type="monotone" dataKey="avg7" stroke="rgba(255,255,255,0.55)" strokeWidth={1.4}
                dot={false} strokeDasharray="4 4" connectNulls />
            </AreaChart>
          </ResponsiveContainer>
        )}
      </div>

      {data && data.explanation && (
        <details className="mchart__explain">
          <summary>How this is calculated</summary>
          <div>{data.explanation}</div>
        </details>
      )}

      {data && (flags.length > 0 || insights.length > 0 || correlations.length > 0) && (
        <div className="mchart__intel">
          {flags.length > 0 && (
            <div className="mchart__panel">
              <div className="mchart__panel-title">Flags</div>
              {flags.map((flag, index) => (
                <div key={`${flag.title}-${index}`} className={`mchart__flag mchart__flag--${flag.severity}`}>
                  <strong>{flag.title}</strong>
                  <span>{flag.detail}</span>
                </div>
              ))}
            </div>
          )}
          {insights.length > 0 && (
            <div className="mchart__panel">
              <div className="mchart__panel-title">Insight</div>
              {insights.map((insight, index) => (
                <div key={`${insight.title}-${index}`} className="mchart__insight">
                  <strong>{insight.title}</strong>
                  <span>{insight.summary}</span>
                </div>
              ))}
            </div>
          )}
          {correlations.length > 0 && (
            <div className="mchart__panel">
              <div className="mchart__panel-title">Related signals</div>
              <div className="mchart__chips">
                {correlations.map((item) => (
                  <span key={item.metric} className="mchart__chip">{item.metric.replace("_", " ")} r={item.r}</span>
                ))}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

function fmt(value: number | null | undefined) {
  if (value === null || value === undefined) return "-";
  return Number.isInteger(value) ? String(value) : value.toFixed(1);
}
