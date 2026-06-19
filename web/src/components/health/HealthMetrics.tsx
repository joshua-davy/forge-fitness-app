import type { HealthMetric } from "@/types";
import "./HealthMetrics.css";

const METRIC_COLOR: Record<string, string> = {
  Sleep: "var(--sleep)",
  HRV: "var(--hrv)",
  "Resting HR": "var(--bad)",
  "Body Battery": "var(--good)",
  Stress: "var(--warn)",
};

function deltaText(d: number | null, unit: string | null): string {
  if (d === null || d === undefined) return "";
  const sign = d > 0 ? "+" : "";
  return `${sign}${d}${unit ?? ""} vs 7d`;
}

export function HealthMetrics({ metrics }: { metrics: HealthMetric[] }) {
  return (
    <div className="hmetrics">
      {metrics.map((m) => {
        const c = METRIC_COLOR[m.name] ?? "var(--text-2)";
        return (
          <div key={m.name} className="hmetric card">
            <div className="hmetric__label" style={{ color: c }}>
              {m.name}
            </div>
            <div className="hmetric__value">
              {m.value ?? "—"}
              {m.unit && <span className="hmetric__unit">{m.unit}</span>}
            </div>
            <div className={`hmetric__delta hmetric__delta--${m.status ?? "neutral"}`}>
              {deltaText(m.delta_7d, m.unit)}
            </div>
          </div>
        );
      })}
    </div>
  );
}
