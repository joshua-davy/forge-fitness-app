import "./RangeMarkerCard.css";

export type RangeTone = "good" | "warn" | "bad" | "low" | "neutral";
export type RangeMode = "higher" | "lower" | "range" | "target";

interface Props {
  label: string;
  value: number | null | undefined;
  unit?: string;
  min: number;
  max: number;
  normalLow?: number;
  normalHigh?: number;
  mode?: RangeMode;
  help?: string;
  onClick?: () => void;
}

export function RangeMarkerCard({
  label,
  value,
  unit,
  min,
  max,
  normalLow,
  normalHigh,
  mode = "range",
  help,
  onClick,
}: Props) {
  const display = value ?? null;
  const percent = display === null ? 50 : clamp(((display - min) / Math.max(max - min, 1)) * 100, 0, 100);
  const tone = toneForValue(display, min, max, normalLow, normalHigh, mode);
  const status = statusLabel(tone, mode);

  return (
    <button
      type="button"
      className={`range-card card range-card--${tone} ${onClick ? "range-card--clickable" : ""}`}
      onClick={onClick}
      disabled={!onClick}
    >
      <div className="range-card__text">
        <div className="range-card__label">{label}</div>
        <div className="range-card__value">
          {display !== null ? (
            <>
              <span>{formatValue(display)}</span>
              {unit && <em>{unit}</em>}
            </>
          ) : (
            <span className="range-card__empty">No data</span>
          )}
        </div>
        <div className="range-card__status">{display === null ? "Missing" : status}</div>
        {help && <div className="range-card__help">{help}</div>}
      </div>
      <div className="range-card__rail" aria-hidden="true">
        <span className="range-card__track" />
        {normalLow !== undefined && normalHigh !== undefined && (
          <span
            className="range-card__normal"
            style={{
              bottom: `${clamp(((normalLow - min) / Math.max(max - min, 1)) * 100, 0, 100)}%`,
              height: `${Math.max(4, clamp(((normalHigh - normalLow) / Math.max(max - min, 1)) * 100, 0, 100))}%`,
            }}
          />
        )}
        <span className="range-card__dot" style={{ bottom: `${percent}%` }} />
      </div>
    </button>
  );
}

function toneForValue(
  value: number | null,
  min: number,
  max: number,
  normalLow: number | undefined,
  normalHigh: number | undefined,
  mode: RangeMode,
): RangeTone {
  if (value === null) return "neutral";
  if (mode === "higher") {
    const warnAt = normalLow ?? min + (max - min) * 0.55;
    const goodAt = normalHigh ?? min + (max - min) * 0.75;
    if (value >= goodAt) return "good";
    if (value >= warnAt) return "warn";
    return "bad";
  }
  if (mode === "lower") {
    const goodHigh = normalHigh ?? min + (max - min) * 0.38;
    const warnHigh = normalLow ?? min + (max - min) * 0.58;
    if (value <= goodHigh) return value < min + (max - min) * 0.08 ? "low" : "good";
    if (value <= warnHigh) return "warn";
    return "bad";
  }

  const low = normalLow ?? min + (max - min) * 0.35;
  const high = normalHigh ?? min + (max - min) * 0.65;
  if (value < low) return mode === "target" ? "low" : "warn";
  if (value <= high) return "good";
  return value > high + (max - min) * 0.18 ? "bad" : "warn";
}

function statusLabel(tone: RangeTone, mode: RangeMode) {
  if (tone === "good") return mode === "target" ? "In range" : "Normal";
  if (tone === "low") return "Low";
  if (tone === "warn") return mode === "lower" ? "Elevated" : "Watch";
  if (tone === "bad") return mode === "lower" ? "High" : "Poor";
  return "No range";
}

function formatValue(value: number) {
  if (Math.abs(value) >= 1000) return Math.round(value).toLocaleString();
  if (Number.isInteger(value)) return String(value);
  return value.toFixed(Math.abs(value) < 10 ? 1 : 0);
}

function clamp(value: number, low: number, high: number) {
  return Math.min(high, Math.max(low, value));
}
