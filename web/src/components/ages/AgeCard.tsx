import { motion } from "framer-motion";
import type { AgeDriver } from "@/types";
import "./AgeCard.css";

interface Props {
  kind: "fitness" | "biological";
  age: number | null;
  actualAge: number;
  delta: number | null;
  status: string | null;
  drivers: AgeDriver[];
  onClick?: () => void;
}

const STATUS_TONE: Record<string, string> = {
  Excellent: "good", Good: "good", Optimal: "good", Stable: "good",
  Fair: "warn", Watch: "warn", "Needs Work": "bad", "Elevated Risk": "bad",
};

const RING_COLOR: Record<string, string> = {
  Excellent: "#6BE3A4", Good: "#6BE3A4", Optimal: "#6BE3A4", Stable: "#62E6D0",
  Fair: "#F2C063", Watch: "#F2C063", "Needs Work": "#FF6B6B", "Elevated Risk": "#FF6B6B",
};

export function AgeCard({ kind, age, actualAge, delta, status, drivers, onClick }: Props) {
  const isFitness = kind === "fitness";
  const label = isFitness ? "Fitness Age" : "Biological Age";
  const tone = status ? (STATUS_TONE[status] ?? "neutral") : "neutral";
  const ringColor = status ? (RING_COLOR[status] ?? "#76746E") : "#76746E";

  const size = 120;
  const stroke = 8;
  const r = (size - stroke) / 2;
  const C = 2 * Math.PI * r;
  // Ring shows how much younger/older vs a ±10y range
  const pct = age ? Math.max(0, Math.min(1, (age / 80))) : 0;
  const offset = C * (1 - pct);

  return (
    <div className={`age-card card age-card--${tone}`} onClick={onClick} role={onClick ? "button" : undefined}>
      <div className="age-card__head">
        <div className="card__label">{label}</div>
        {status && <div className={`pill pill--${tone}`}>{status}</div>}
      </div>

      <div className="age-card__body">
        <div className="age-card__ring">
          <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`}>
            <circle cx={size/2} cy={size/2} r={r} fill="none" stroke="rgba(255,255,255,0.06)" strokeWidth={stroke} />
            <motion.circle
              cx={size/2} cy={size/2} r={r} fill="none"
              stroke={ringColor} strokeWidth={stroke} strokeLinecap="round"
              strokeDasharray={C} transform={`rotate(-90 ${size/2} ${size/2})`}
              initial={false}
              animate={{ strokeDashoffset: offset }}
              transition={{ duration: 1, ease: [0.2, 0.8, 0.2, 1] }}
              style={{ filter: `drop-shadow(0 0 8px ${ringColor}55)` }}
            />
          </svg>
          <div className="age-card__ring-center">
            {age ? (
              <>
                <div className="age-card__age">{Math.round(age)}</div>
                <div className="age-card__age-label">yrs</div>
              </>
            ) : (
              <div className="age-card__no-data">—</div>
            )}
          </div>
        </div>

        <div className="age-card__info">
          <div className="age-card__actual">
            <span className="age-card__actual-label">Actual age</span>
            <span className="age-card__actual-val">{actualAge}</span>
          </div>
          {delta !== null && (
            <div className={`age-card__delta age-card__delta--${delta < 0 ? "good" : delta > 0 ? "bad" : "neutral"}`}>
              {delta < 0 ? `${Math.abs(delta)}y younger` : delta > 0 ? `${delta}y older` : "At your age"}
            </div>
          )}
          <div className="age-card__subtitle">
            {isFitness
              ? "Cardiovascular fitness vs age"
              : "Physiological health vs age"}
          </div>
        </div>
      </div>

      {drivers.length > 0 && (
        <div className="age-card__drivers">
          {drivers.slice(0, 5).map((d) => (
            <div key={d.name} className="age-driver">
              <div className="age-driver__name">{d.name}</div>
              <div className="age-driver__bar-wrap">
                <div
                  className={`age-driver__bar age-driver__bar--${d.direction}`}
                  style={{ width: `${Math.min(100, Math.abs(d.adjustment_years) * 20 + 10)}%` }}
                />
              </div>
              <div className={`age-driver__dir age-driver__dir--${d.direction}`}>
                {d.direction === "helping" ? "▼" : d.direction === "hurting" ? "▲" : "–"}
                {" "}{Math.abs(d.adjustment_years)}y
              </div>
            </div>
          ))}
        </div>
      )}

      {!age && (
        <div className="age-card__empty">Sync Garmin to calculate</div>
      )}

      {onClick && age && (
        <div className="age-card__cta">View detail →</div>
      )}
    </div>
  );
}
