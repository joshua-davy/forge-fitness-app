import Constants from "expo-constants";
import type { CoachPayload, Dashboard, DayProgress, Goal, Streak } from "../types";

const BASE: string =
  (Constants.expoConfig?.extra?.apiUrl as string | undefined) ?? "http://localhost:8000";

async function req<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    headers: { "Content-Type": "application/json", ...(init?.headers ?? {}) },
    ...init,
  });
  if (!res.ok) throw new Error(`${res.status} ${path}`);
  if (res.status === 204) return undefined as T;
  return res.json() as Promise<T>;
}

export const api = {
  todayGoals: () => req<Goal[]>("/api/goals/today"),
  tomorrowGoals: () => req<Goal[]>("/api/goals/tomorrow"),
  createGoal: (text: string, queued = false, date?: string) =>
    req<Goal>("/api/goals", { method: "POST", body: JSON.stringify({ text, queued, date }) }),
  updateGoal: (id: number, patch: Partial<Goal>) =>
    req<Goal>(`/api/goals/${id}`, { method: "PATCH", body: JSON.stringify(patch) }),
  deleteGoal: (id: number) => req<void>(`/api/goals/${id}`, { method: "DELETE" }),
  pushRemaining: () =>
    req<{ moved: number; to_date: string }>("/api/goals/push-remaining", { method: "POST" }),
  streak: () => req<Streak>("/api/goals/streak"),
  dayProgress: () => req<DayProgress>("/api/day-progress"),
  dashboard: () => req<Dashboard>("/api/dashboard/today"),
  coach: () => req<CoachPayload>("/api/coach/today"),
};
