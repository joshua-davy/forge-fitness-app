import { motion } from "framer-motion";
import type { Ring } from "@/types";
import "./HealthRings.css";

interface Props {
  rings: Ring[];
}

function HealthRing({ ring }: { ring: Ring }) {
  const size = 110;
  const stroke = 9;
  const r = (size - stroke) / 2;
  const cx = size / 2;
  const cy = size / 2;
  const C = 2 * Math.PI * r;
  const pct = ring.value / ring.target;
  const offset = C * (1 - Math.max(0, Math.min(1, pct)));
  const colorVar = ringColor(ring);

  return (
    <div className="hring">
      <div className="hring__visual" style={{ width: size, height: size }}>
        <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`}>
          <circle
            cx={cx}
            cy={cy}
            r={r}
            fill="none"
            stroke="rgba(255,255,255,0.06)"
            strokeWidth={stroke}
          />
          <motion.circle
            cx={cx}
            cy={cy}
            r={r}
            fill="none"
            stroke={colorVar}
            strokeWidth={stroke}
            strokeLinecap="round"
            strokeDasharray={C}
            transform={`rotate(-90 ${cx} ${cy})`}
            initial={false}
            animate={{ strokeDashoffset: offset }}
            transition={{ duration: 0.9, ease: [0.2, 0.8, 0.2, 1] }}
            style={{ filter: `drop-shadow(0 0 8px ${colorVar})` }}
          />
        </svg>
        <div className="hring__value">
          {ring.value}
          <span className="hring__unit">/{ring.target}</span>
        </div>
      </div>
      <div className="hring__label">{ring.label}</div>
    </div>
  );
}

export function HealthRings({ rings }: Props) {
  return (
    <div className="hrings card">
      <div className="card__label">Vitals</div>
      <div className="hrings__row">
        {rings.map((r) => (
          <HealthRing key={r.label} ring={r} />
        ))}
      </div>
    </div>
  );
}

function ringColor(ring: Ring) {
  const ratio = ring.target > 0 ? ring.value / ring.target : 0;
  if (ratio < 0.4) return "var(--bad)";
  if (ratio < 0.6) return "var(--strain)";
  if (ratio < 0.75) return "var(--warn)";
  return "var(--good)";
}
