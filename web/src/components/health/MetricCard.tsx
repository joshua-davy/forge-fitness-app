import "./MetricCard.css";

interface Props {
  label: string;
  value: number | null;
  unit?: string;
  status?: "good" | "warn" | "bad" | null;
  delta?: number | null;
  deltaUnit?: string;
  sublabel?: string;
  color?: string;
  onClick?: () => void;
}

export function MetricCard({ label, value, unit, status, delta, deltaUnit, sublabel, color, onClick }: Props) {
  return (
    <div
      className={`mcard card ${status ? `mcard--${status}` : ""} ${onClick ? "mcard--clickable" : ""}`}
      onClick={onClick}
    >
      <div className="mcard__label" style={color && !status ? { color } : undefined}>{label}</div>
      <div className="mcard__value">
        {value !== null && value !== undefined ? (
          <>
            <span className="mcard__num">{value}</span>
            {unit && <span className="mcard__unit">{unit}</span>}
          </>
        ) : (
          <span className="mcard__empty">—</span>
        )}
      </div>
      {delta !== null && delta !== undefined && (
        <div className={`mcard__delta ${delta > 0 ? "mcard__delta--up" : delta < 0 ? "mcard__delta--down" : ""}`}>
          {delta > 0 ? "+" : ""}{delta}{deltaUnit ?? ""}
        </div>
      )}
      {sublabel && <div className="mcard__sub">{sublabel}</div>}
      {onClick && <div className="mcard__cta">→</div>}
    </div>
  );
}
