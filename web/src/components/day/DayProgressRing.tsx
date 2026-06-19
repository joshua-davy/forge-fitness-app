import { motion } from "framer-motion";
import { useEffect, useState } from "react";
import type { DayProgress } from "@/types";
import "./DayProgressRing.css";

interface Props {
  data: DayProgress | null;
  size?: number;
}

const PHASE_COLORS: Record<DayProgress["phase"], [string, string]> = {
  SLEEPING: ["#4759a9", "#8f7cff"],
  MORNING: ["#ffd27d", "#ffe07a"],
  MIDDAY: ["#ffe07a", "#ffb066"],
  AFTERNOON: ["#ffb066", "#ff9b5f"],
  EVENING: ["#ff7a59", "#ff6b9a"],
  BEDTIME: ["#8f7cff", "#5fb5ff"],
  "PAST BEDTIME": ["#4759a9", "#2c3a78"],
};

function formatRemaining(secs: number): string {
  if (secs <= 0) return "—";
  const h = Math.floor(secs / 3600);
  const m = Math.floor((secs % 3600) / 60);
  if (h > 0) return `${h}h ${m}m left`;
  return `${m}m left`;
}

function formatTimeOnly(iso: string): string {
  try {
    const d = new Date(iso);
    return d.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", hour12: false });
  } catch {
    return "—";
  }
}

export function DayProgressRing({ data, size = 168 }: Props) {
  const [clock, setClock] = useState(new Date());
  useEffect(() => {
    const id = window.setInterval(() => setClock(new Date()), 1000 * 30);
    return () => window.clearInterval(id);
  }, []);

  const stroke = 10;
  const r = (size - stroke) / 2;
  const cx = size / 2;
  const cy = size / 2;
  const C = 2 * Math.PI * r;

  const pct = data?.percent ?? 0;
  const phase = data?.phase ?? "MORNING";
  const [c1, c2] = PHASE_COLORS[phase];

  const wake = data ? formatTimeOnly(data.wake_iso) : "—";
  const sleep = data ? formatTimeOnly(data.sleep_iso) : "—";
  const nowStr = clock.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", hour12: false });

  const offset = C * (1 - pct);

  return (
    <div className="dayring">
      <div className="dayring__visual" style={{ width: size, height: size }}>
        <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`} className="dayring__svg">
          <defs>
            <linearGradient id="dayring-grad" x1="0" y1="0" x2="1" y2="1">
              <stop offset="0%" stopColor={c1} />
              <stop offset="100%" stopColor={c2} />
            </linearGradient>
            <filter id="dayring-glow">
              <feGaussianBlur stdDeviation="3" />
            </filter>
          </defs>
          {/* Track */}
          <circle
            cx={cx}
            cy={cy}
            r={r}
            fill="none"
            stroke="rgba(255,255,255,0.06)"
            strokeWidth={stroke}
          />
          {/* Progress */}
          <motion.circle
            cx={cx}
            cy={cy}
            r={r}
            fill="none"
            stroke="url(#dayring-grad)"
            strokeWidth={stroke}
            strokeLinecap="round"
            strokeDasharray={C}
            transform={`rotate(-90 ${cx} ${cy})`}
            initial={false}
            animate={{ strokeDashoffset: offset }}
            transition={{ duration: 0.9, ease: [0.2, 0.8, 0.2, 1] }}
            style={{ filter: "drop-shadow(0 0 6px " + c1 + "55)" }}
          />
        </svg>
        <div className="dayring__center">
          <div className="dayring__pct">{Math.round(pct * 100)}<span className="dayring__pct-sym">%</span></div>
          <div className="dayring__phase">{phase}</div>
          <div className="dayring__clock">{nowStr}</div>
        </div>
      </div>

      <div className="dayring__meta">
        <div className="dayring__status">{data?.status ?? "—"}</div>
        <div className="dayring__remaining">{data ? formatRemaining(data.remaining_seconds) : "—"}</div>
        <div className="dayring__window">
          <span>{wake}</span>
          <span className="dayring__window-sep">→</span>
          <span>{sleep}</span>
        </div>
      </div>
    </div>
  );
}
