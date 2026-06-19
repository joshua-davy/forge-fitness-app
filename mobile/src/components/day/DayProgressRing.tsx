import { useEffect, useState } from "react";
import { View, Text, StyleSheet } from "react-native";
import Svg, { Circle, Defs, LinearGradient, Stop } from "react-native-svg";
import type { DayProgress } from "../../types";
import { theme } from "../../theme";

const PHASE_COLORS: Record<string, [string, string]> = {
  SLEEPING: ["#4759a9", "#8f7cff"],
  MORNING: ["#ffd27d", "#ffe07a"],
  MIDDAY: ["#ffe07a", "#ffb066"],
  AFTERNOON: ["#ffb066", "#ff9b5f"],
  EVENING: ["#ff7a59", "#ff6b9a"],
  BEDTIME: ["#8f7cff", "#5fb5ff"],
  "PAST BEDTIME": ["#4759a9", "#2c3a78"],
};

function formatRemaining(s: number) {
  if (s <= 0) return "—";
  const h = Math.floor(s / 3600);
  const m = Math.floor((s % 3600) / 60);
  return h ? `${h}h ${m}m left` : `${m}m left`;
}

function timeOnly(iso: string) {
  try {
    return new Date(iso).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", hour12: false });
  } catch {
    return "—";
  }
}

export function DayProgressRing({ data, size = 144 }: { data: DayProgress | null; size?: number }) {
  const [clock, setClock] = useState(new Date());
  useEffect(() => {
    const id = setInterval(() => setClock(new Date()), 30_000);
    return () => clearInterval(id);
  }, []);

  const stroke = 10;
  const r = (size - stroke) / 2;
  const cx = size / 2;
  const cy = size / 2;
  const C = 2 * Math.PI * r;
  const pct = data?.percent ?? 0;
  const [c1, c2] = PHASE_COLORS[data?.phase ?? "MORNING"];
  const offset = C * (1 - pct);

  return (
    <View style={styles.row}>
      <View style={{ width: size, height: size }}>
        <Svg width={size} height={size}>
          <Defs>
            <LinearGradient id="g" x1="0" y1="0" x2="1" y2="1">
              <Stop offset="0%" stopColor={c1} />
              <Stop offset="100%" stopColor={c2} />
            </LinearGradient>
          </Defs>
          <Circle cx={cx} cy={cy} r={r} stroke="rgba(255,255,255,0.06)" strokeWidth={stroke} fill="none" />
          <Circle
            cx={cx}
            cy={cy}
            r={r}
            stroke="url(#g)"
            strokeWidth={stroke}
            strokeLinecap="round"
            strokeDasharray={`${C}, ${C}`}
            strokeDashoffset={offset}
            fill="none"
            transform={`rotate(-90 ${cx} ${cy})`}
          />
        </Svg>
        <View style={styles.center}>
          <Text style={styles.pct}>{Math.round(pct * 100)}%</Text>
          <Text style={styles.phase}>{data?.phase ?? "—"}</Text>
          <Text style={styles.clock}>
            {clock.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", hour12: false })}
          </Text>
        </View>
      </View>
      <View style={styles.meta}>
        <Text style={styles.status}>{data?.status ?? "—"}</Text>
        <Text style={styles.remaining}>{data ? formatRemaining(data.remaining_seconds) : "—"}</Text>
        <Text style={styles.window}>
          {data ? `${timeOnly(data.wake_iso)} → ${timeOnly(data.sleep_iso)}` : "—"}
        </Text>
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  row: { flexDirection: "row", alignItems: "center", gap: 22, flexWrap: "wrap" },
  center: {
    position: "absolute",
    top: 0,
    left: 0,
    right: 0,
    bottom: 0,
    alignItems: "center",
    justifyContent: "center",
  },
  pct: {
    fontFamily: theme.font.display,
    fontSize: 30,
    color: theme.text.primary,
    letterSpacing: -1,
  },
  phase: {
    fontFamily: theme.font.mono,
    fontSize: 9,
    letterSpacing: 1.6,
    color: theme.text.secondary,
    marginTop: 3,
  },
  clock: {
    fontFamily: theme.font.mono,
    fontSize: 10,
    color: theme.text.tertiary,
    marginTop: 1,
  },
  meta: { flexShrink: 1, gap: 4 },
  status: {
    fontFamily: theme.font.display,
    fontSize: 18,
    color: theme.text.primary,
    letterSpacing: -0.3,
  },
  remaining: { fontFamily: theme.font.mono, fontSize: 11, color: theme.text.secondary },
  window: { fontFamily: theme.font.mono, fontSize: 10, color: theme.text.tertiary },
});
