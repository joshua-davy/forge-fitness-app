import { useCallback, useEffect, useState } from "react";
import { RefreshControl, ScrollView, StyleSheet, Text, View } from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";
import { api } from "../lib/api";
import { theme } from "../theme";
import { DayProgressRing } from "../components/day/DayProgressRing";
import { GoalTicker } from "../components/goals/GoalTicker";
import type { CoachPayload, Dashboard, DayProgress, Goal } from "../types";

export function DashboardScreen() {
  const [today, setToday] = useState<Goal[]>([]);
  const [day, setDay] = useState<DayProgress | null>(null);
  const [dash, setDash] = useState<Dashboard | null>(null);
  const [coach, setCoach] = useState<CoachPayload | null>(null);
  const [refreshing, setRefreshing] = useState(false);

  const refresh = useCallback(async () => {
    try {
      const [t, d, db, c] = await Promise.all([
        api.todayGoals(),
        api.dayProgress(),
        api.dashboard(),
        api.coach(),
      ]);
      setToday(t);
      setDay(d);
      setDash(db);
      setCoach(c);
    } catch {}
  }, []);

  useEffect(() => {
    refresh();
    const id = setInterval(refresh, 60_000);
    return () => clearInterval(id);
  }, [refresh]);

  return (
    <SafeAreaView style={styles.safe}>
      <ScrollView
        contentContainerStyle={styles.scroll}
        refreshControl={
          <RefreshControl
            refreshing={refreshing}
            onRefresh={async () => {
              setRefreshing(true);
              await refresh();
              setRefreshing(false);
            }}
            tintColor={theme.text.tertiary}
          />
        }
      >
        <View style={styles.header}>
          <Text style={styles.eyebrow}>FORGE / DAILY COMMAND CENTRE</Text>
          <Text style={styles.title}>Today</Text>
          <Text style={styles.date}>{dash?.active_date ?? ""}</Text>
        </View>

        <GoalTicker goals={today} />

        <View style={styles.card}>
          <Text style={styles.cardLabel}>Day progress</Text>
          <DayProgressRing data={day} />
        </View>

        {coach && (
          <View style={styles.card}>
            <Text style={styles.cardLabel}>Coach</Text>
            <Text style={styles.summary}>{coach.summary}</Text>
            {coach.recommendations.map((r, i) => (
              <View key={i} style={[styles.rec, recTone(r.tone)]}>
                <Text style={styles.recTitle}>{r.title}</Text>
                <Text style={styles.recBody}>{r.body}</Text>
              </View>
            ))}
          </View>
        )}

        {dash && (
          <View style={styles.card}>
            <Text style={styles.cardLabel}>Vitals</Text>
            {dash.metrics.map((m) => (
              <View key={m.name} style={styles.metricRow}>
                <Text style={styles.metricLabel}>{m.name}</Text>
                <Text style={styles.metricValue}>
                  {m.value ?? "—"}
                  {m.unit ? ` ${m.unit}` : ""}
                </Text>
              </View>
            ))}
          </View>
        )}
      </ScrollView>
    </SafeAreaView>
  );
}

function recTone(t: string) {
  switch (t) {
    case "good":
      return { borderLeftColor: theme.semantic.good };
    case "warn":
      return { borderLeftColor: theme.semantic.warn };
    case "bad":
      return { borderLeftColor: theme.semantic.bad };
    default:
      return { borderLeftColor: theme.semantic.below };
  }
}

const styles = StyleSheet.create({
  safe: { flex: 1, backgroundColor: theme.bg.base },
  scroll: { padding: 18, gap: 14 },
  header: { paddingBottom: 16, borderBottomWidth: 1, borderBottomColor: theme.border.soft, gap: 4 },
  eyebrow: { fontFamily: theme.font.mono, fontSize: 9, letterSpacing: 2, color: theme.text.tertiary },
  title: {
    fontFamily: theme.font.display,
    fontSize: 30,
    color: theme.text.primary,
    letterSpacing: -1,
  },
  date: { fontFamily: theme.font.mono, fontSize: 11, color: theme.text.secondary },
  card: {
    backgroundColor: theme.bg.card,
    borderWidth: 1,
    borderColor: theme.border.soft,
    borderRadius: theme.radius.lg,
    padding: theme.space.lg,
    gap: 12,
  },
  cardLabel: {
    fontFamily: theme.font.mono,
    fontSize: 10,
    letterSpacing: 1.8,
    color: theme.text.tertiary,
  },
  summary: { fontFamily: theme.font.display, fontSize: 20, color: theme.text.primary, lineHeight: 26 },
  rec: { borderLeftWidth: 3, paddingLeft: 12, paddingVertical: 8, gap: 3 },
  recTitle: {
    fontFamily: theme.font.mono,
    fontSize: 10,
    letterSpacing: 1.4,
    color: theme.text.secondary,
  },
  recBody: { fontFamily: theme.font.body, fontSize: 14, color: theme.text.primary, lineHeight: 20 },
  metricRow: { flexDirection: "row", justifyContent: "space-between", paddingVertical: 4 },
  metricLabel: { fontFamily: theme.font.mono, fontSize: 11, color: theme.text.tertiary },
  metricValue: { fontFamily: theme.font.display, fontSize: 18, color: theme.text.primary },
});
