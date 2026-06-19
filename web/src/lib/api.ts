import type { AuthPayload, AuthUser, CoachPayload, Dashboard, DayProgress, GarminStatus, Goal, InsightsPayload, MetricSeries, PolishResponse, ProfilePayload, SpecialMetric, Streak } from "@/types";

const configuredBase = import.meta.env.VITE_API_URL as string | undefined;
const BASE = configuredBase || (window.location.hostname === "localhost" || window.location.hostname === "127.0.0.1"
  ? "http://127.0.0.1:8001"
  : "");

function withParams(path: string, params: Record<string, string | number | null | undefined>) {
  const qs = new URLSearchParams();
  Object.entries(params).forEach(([key, value]) => {
    if (value !== null && value !== undefined && value !== "") qs.set(key, String(value));
  });
  return qs.size ? `${path}?${qs.toString()}` : path;
}

async function req<T>(path: string, init?: RequestInit): Promise<T> {
  const token = localStorage.getItem("forge_auth_token");
  const res = await fetch(`${BASE}${path}`, {
    headers: {
      "Content-Type": "application/json",
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...(init?.headers ?? {}),
    },
    ...init,
  });
  const contentType = res.headers.get("content-type") || "";
  if (!res.ok) {
    const body = await res.text().catch(() => "");
    let msg = body;
    try { msg = JSON.parse(body)?.detail || body; } catch {}
    throw new Error(`${res.status}: ${msg || path}`);
  }
  if (res.status === 204) return undefined as T;
  if (!contentType.includes("application/json")) {
    const sample = await res.text().catch(() => "");
    throw new Error(`Expected JSON from API but received ${contentType || "unknown content"} for ${path}. ${sample.slice(0, 80)}`);
  }
  return res.json() as Promise<T>;
}

export const api = {
  // Account foundation
  authSignup: (payload: { email: string; password: string; display_name: string }) =>
    req<AuthPayload>("/api/auth/signup", { method: "POST", body: JSON.stringify(payload) }),
  authLogin: (payload: { email: string; password: string }) =>
    req<AuthPayload>("/api/auth/login", { method: "POST", body: JSON.stringify(payload) }),
  authMe: () => req<{ user: AuthUser }>("/api/auth/me"),
  authLogout: () => req<{ ok: boolean }>("/api/auth/logout", { method: "POST" }),

  // Dashboard
  dashboard: (date?: string | null) => req<Dashboard>(withParams("/api/dashboard/today", { date })),
  dayProgress: () => req<DayProgress>("/api/day-progress"),
  profile: () => req<ProfilePayload>("/api/profile"),
  updateProfile: (payload: Partial<Pick<ProfilePayload, "name" | "date_of_birth" | "height_cm" | "weight_kg" | "body_fat_pct" | "muscle_mass_kg">>) =>
    req<ProfilePayload>("/api/profile", { method: "PUT", body: JSON.stringify(payload) }),

  // Garmin
  garminStatus: () => req<GarminStatus>("/api/sync/garmin/status"),
  syncGarmin: () => req<{ status: string; date: string }>("/api/sync/garmin", { method: "POST" }),
  syncGarminHistory: (days = 365) =>
    req<{ synced: number; failed: number; skipped: number }>(`/api/sync/garmin/history?days=${days}`, { method: "POST" }),
  saveBodyComposition: (payload: { date?: string; weight_kg?: number | null; body_fat_pct?: number | null; muscle_mass_kg?: number | null }) =>
    req<{ date: string; weight_kg: number | null; body_fat_pct: number | null; muscle_mass_kg: number | null; bmi: number | null }>("/api/body-composition", {
      method: "POST",
      body: JSON.stringify(payload),
    }),

  // Metrics
  metricSeries: (metric: string, range = "30d", date?: string | null) =>
    req<MetricSeries>(withParams(`/api/metrics/${metric}`, { range, date })),
  insights: (range = "90d", date?: string | null) => req<InsightsPayload>(withParams("/api/insights", { range, date })),
  specialMetrics: (range = "90d", date?: string | null) =>
    req<{ range: string; generated_at: string; metrics: Record<string, SpecialMetric> }>(withParams("/api/special-metrics", { range, date })),
  fitnessAge: () => req<Record<string, unknown>>("/api/fitness-age"),
  biologicalAge: () => req<Record<string, unknown>>("/api/biological-age"),

  // Coach
  coachToday: () => req<CoachPayload>("/api/coach/today"),
  coachGenerate: () => req<CoachPayload>("/api/coach/generate", { method: "POST" }),
  coachHistory: (limit = 14) => req<CoachPayload[]>(`/api/coach/history?limit=${limit}`),

  // Goals
  todayGoals: () => req<Goal[]>("/api/goals/today"),
  tomorrowGoals: () => req<Goal[]>("/api/goals/tomorrow"),
  createGoal: (text: string, queued = false, date?: string) =>
    req<Goal>("/api/goals", { method: "POST", body: JSON.stringify({ text, queued, date }) }),
  updateGoal: (id: number, patch: Partial<Pick<Goal, "text" | "done" | "queued" | "sort_order">>) =>
    req<Goal>(`/api/goals/${id}`, { method: "PATCH", body: JSON.stringify(patch) }),
  deleteGoal: (id: number) => req<void>(`/api/goals/${id}`, { method: "DELETE" }),
  reorder: (items: { id: number; sort_order: number }[]) =>
    req<{ updated: number }>("/api/goals/reorder", { method: "POST", body: JSON.stringify({ items }) }),
  pushRemaining: () =>
    req<{ moved: number; to_date: string }>("/api/goals/push-remaining", { method: "POST" }),
  streak: () => req<Streak>("/api/goals/streak"),
  polish: (text: string) =>
    req<PolishResponse>("/api/goals/polish", { method: "POST", body: JSON.stringify({ text }) }),
};
