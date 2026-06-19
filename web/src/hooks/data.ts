import { useCallback, useEffect, useRef, useState } from "react";
import { api } from "@/lib/api";
import type { CoachPayload, Dashboard, DayProgress, GarminStatus, Goal, InsightsPayload, Streak } from "@/types";

function usePoll<T>(fetcher: () => Promise<T>, intervalMs = 60_000) {
  const [data, setData] = useState<T | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<Error | null>(null);
  const refresh = useCallback(async () => {
    try {
      const d = await fetcher();
      setData(d); setError(null);
    } catch (e) { setError(e as Error); }
    finally { setLoading(false); }
  }, [fetcher]);
  useEffect(() => {
    refresh();
    const id = window.setInterval(refresh, intervalMs);
    return () => window.clearInterval(id);
  }, [refresh, intervalMs]);
  return { data, loading, error, refresh };
}

export function useDayProgress() {
  return usePoll(api.dayProgress, 60_000);
}

export function useDashboard(date?: string | null) {
  const fetcher = useCallback(() => api.dashboard(date), [date]);
  return usePoll(fetcher, 60_000);
}

export function useCoach() {
  return usePoll(api.coachToday, 5 * 60_000);
}

export function useGarminStatus() {
  return usePoll(api.garminStatus, 30_000);
}

export function useInsights(date?: string | null) {
  const fetcher = useCallback(() => api.insights("90d", date), [date]);
  return usePoll<InsightsPayload>(fetcher, 5 * 60_000);
}

export function useGoals() {
  const [today, setToday] = useState<Goal[]>([]);
  const [tomorrow, setTomorrow] = useState<Goal[]>([]);
  const [streak, setStreak] = useState<Streak | null>(null);
  const [loading, setLoading] = useState(true);
  const inflight = useRef(false);

  const refresh = useCallback(async () => {
    if (inflight.current) return;
    inflight.current = true;
    try {
      const [t, tm, s] = await Promise.all([api.todayGoals(), api.tomorrowGoals(), api.streak()]);
      setToday(t); setTomorrow(tm); setStreak(s);
    } finally { inflight.current = false; setLoading(false); }
  }, []);

  useEffect(() => { refresh(); }, [refresh]);

  const create = useCallback(async (text: string, target: "today" | "tomorrow") => {
    const opt: Goal = { id: -Math.random(), date: "", text, done: false, done_at: null, queued: false, sort_order: 9999, created_at: "", updated_at: "" };
    if (target === "today") setToday(p => [...p, opt]);
    else setTomorrow(p => [...p, opt]);
    try {
      const real = await api.createGoal(text, false, target === "tomorrow" ? getTomorrowISO() : undefined);
      if (target === "today") setToday(p => p.map(g => g.id === opt.id ? real : g));
      else setTomorrow(p => p.map(g => g.id === opt.id ? real : g));
    } catch { refresh(); }
  }, [refresh]);

  const update = useCallback(async (id: number, patch: Partial<Pick<Goal,"text"|"done"|"queued"|"sort_order">>) => {
    setToday(p => p.map(g => g.id === id ? { ...g, ...patch } : g));
    setTomorrow(p => p.map(g => g.id === id ? { ...g, ...patch } : g));
    try {
      await api.updateGoal(id, patch);
      if (patch.done !== undefined) { const s = await api.streak(); setStreak(s); }
    } catch { refresh(); }
  }, [refresh]);

  const remove = useCallback(async (id: number) => {
    setToday(p => p.filter(g => g.id !== id));
    setTomorrow(p => p.filter(g => g.id !== id));
    try { await api.deleteGoal(id); } catch { refresh(); }
  }, [refresh]);

  const reorder = useCallback(async (target: "today"|"tomorrow", ordered: Goal[]) => {
    if (target === "today") setToday(ordered); else setTomorrow(ordered);
    try { await api.reorder(ordered.map((g, i) => ({ id: g.id, sort_order: i }))); } catch { refresh(); }
  }, [refresh]);

  const pushRemaining = useCallback(async () => {
    try { await api.pushRemaining(); refresh(); } catch {}
  }, [refresh]);

  return { today, tomorrow, streak, loading, refresh, create, update, remove, reorder, pushRemaining };
}

function getTomorrowISO() {
  const d = new Date(); d.setDate(d.getDate() + 1);
  return d.toISOString().slice(0, 10);
}
