import { useEffect, useMemo, useState } from "react";
import { View, Text, StyleSheet } from "react-native";
import type { Goal } from "../../types";
import { theme } from "../../theme";

export function GoalTicker({ goals }: { goals: Goal[] }) {
  const pending = useMemo(() => goals.filter((g) => !g.done), [goals]);
  const done = goals.length - pending.length;
  const [idx, setIdx] = useState(0);

  useEffect(() => {
    if (idx >= pending.length) setIdx(0);
  }, [pending.length, idx]);

  useEffect(() => {
    if (pending.length < 2) return;
    const id = setInterval(() => setIdx((i) => (i + 1) % pending.length), 5000);
    return () => clearInterval(id);
  }, [pending.length]);

  const empty = goals.length === 0;
  const allDone = !empty && pending.length === 0;
  let body: string;
  let color = theme.text.primary;
  if (empty) {
    body = "No goals set for today — add one to get rolling.";
    color = theme.text.tertiary;
  } else if (allDone) {
    body = "✓ All goals done — solid day.";
    color = theme.semantic.good;
  } else {
    body = pending[idx]?.text ?? "";
  }

  return (
    <View style={[styles.row, allDone && styles.rowGood]}>
      <View style={styles.led} />
      <Text style={styles.label}>GOALS</Text>
      <Text style={[styles.body, { color }]} numberOfLines={1}>
        {body}
      </Text>
      <View style={[styles.count, allDone && styles.countGood]}>
        <Text style={[styles.countText, allDone && { color: theme.semantic.good }]}>
          {done}/{goals.length}
        </Text>
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  row: {
    height: 56,
    paddingHorizontal: 18,
    borderRadius: 14,
    backgroundColor: theme.bg.raised,
    borderWidth: 1,
    borderColor: theme.border.soft,
    flexDirection: "row",
    alignItems: "center",
    gap: 14,
  },
  rowGood: { borderColor: "rgba(107,227,164,0.22)" },
  led: {
    width: 7,
    height: 7,
    borderRadius: 4,
    backgroundColor: theme.semantic.good,
  },
  label: {
    fontFamily: theme.font.mono,
    fontSize: 10,
    letterSpacing: 2,
    color: theme.text.tertiary,
  },
  body: {
    flex: 1,
    fontFamily: theme.font.mono,
    fontSize: 13,
  },
  count: {
    paddingHorizontal: 10,
    paddingVertical: 3,
    borderRadius: 999,
    backgroundColor: "rgba(255,255,255,0.06)",
    borderWidth: 1,
    borderColor: theme.border.soft,
  },
  countGood: {
    backgroundColor: "rgba(107,227,164,0.1)",
    borderColor: "rgba(107,227,164,0.3)",
  },
  countText: { fontFamily: theme.font.mono, fontSize: 11, color: theme.text.secondary },
});
