export type ISODate = string;
export type ISODateTime = string;

export interface Goal {
  id: number; date: ISODate; text: string; done: boolean;
  done_at: ISODateTime | null; queued: boolean; sort_order: number;
  created_at: ISODateTime; updated_at: ISODateTime;
}

export interface Streak { count: number; last_processed_date: ISODate | null; }

export interface DayProgress {
  percent: number; phase: string; status: string;
  remaining_seconds: number; wake_iso: string; sleep_iso: string; now_iso: string;
}

export interface AgeDriver {
  name: string; value: number | null; unit: string;
  adjustment_years: number; direction: "helping" | "hurting" | "neutral";
}

export interface Dashboard {
  active_date: ISODate; has_garmin_data: boolean; actual_age: number;
  profile?: {
    name: string;
    email: string | null;
    date_of_birth: ISODate;
    height_cm: number;
  };
  age_windows?: {
    fitness_age: Partial<Record<"7d" | "30d" | "all", number | null>>;
    biological_age: Partial<Record<"7d" | "30d" | "all", number | null>>;
  };
  day_progress: DayProgress;
  fitness_age: number | null; fitness_age_status: string | null; fitness_age_delta: number | null;
  fitness_age_drivers: AgeDriver[];
  biological_age: number | null; biological_age_status: string | null; biological_age_delta: number | null;
  biological_age_drivers: AgeDriver[];
  rings: { label: string; value: number; target: number; color: string }[];
  metrics: {
    recovery: number | null; readiness: number | null; strain: number | null; target_strain: number | null;
    sleep_score: number | null; sleep_hours: number | null; deep_sleep_hours: number | null;
    rem_sleep_hours: number | null; awake_time_hours: number | null; sleep_debt_hours: number | null;
    sleep_need_hours: number | null;
    hrv: number | null; hrv_baseline: number | null; rhr: number | null; rhr_baseline: number | null;
    max_hr: number | null; hr_recovery: number | null;
    body_battery: number | null; stress: number | null; spo2: number | null;
    respiration: number | null; steps: number | null; active_calories: number | null;
    active_minutes: number | null; moderate_minutes: number | null; vigorous_minutes: number | null;
    distance_km: number | null; floors: number | null;
    vo2max: number | null; cardio_load: number | null; load_balance: number | null;
    weight_kg: number | null; body_fat_pct: number | null; muscle_mass_kg: number | null; bmi: number | null;
  };
  special_metrics?: Record<string, SpecialMetric>;
  streak: number; goals_total: number; goals_completed: number; goals_queued: number;
}

export interface ProfilePayload {
  name: string;
  email: string | null;
  date_of_birth: ISODate | null;
  sex?: string;
  height_cm: number | null;
  actual_age: number | null;
  weight_kg: number | null;
  body_fat_pct: number | null;
  muscle_mass_kg: number | null;
  bmi: number | null;
}

export interface AuthUser {
  id: number;
  email: string;
  display_name: string;
  email_verified: boolean;
  created_at: string | null;
}

export interface AuthPayload {
  token: string;
  token_type: "bearer";
  user: AuthUser;
}

export interface SpecialMetric {
  key: string;
  label: string;
  value: number | string | null;
  unit: string;
  score: number | null;
  status: "good" | "watch" | "alert" | "info" | "no_data" | string;
  tone: "good" | "warn" | "bad" | "low" | "neutral" | string;
  summary: string;
  data_quality: "high" | "medium" | "low" | "limited" | string;
  inputs: string[];
  details: string[];
}

export interface MetricFlag {
  date: ISODate | null;
  severity: "info" | "watch" | "alert";
  title: string;
  detail: string;
  metric: string;
}

export interface InsightCard {
  id?: string;
  title: string;
  summary: string;
  confidence: "low" | "medium" | "high";
  metric: string;
  evidence?: string[];
}

export interface MetricSeries {
  metric: string; label: string; unit: string; range: string; status: string; explanation?: string;
  series: { date: ISODate; value: number }[];
  moving_avg_7d?: { date: ISODate; value: number | null }[];
  coverage?: { covered_days: number; expected_days: number; coverage_pct: number };
  comparison?: { delta: number | null; delta_pct: number | null; previous_avg: number | null };
  stats: {
    min: number | null; max: number | null; avg: number | null; latest: number | null;
    count: number; std?: number | null; trend?: string;
  };
  flags?: MetricFlag[];
  insights?: InsightCard[];
  correlations?: { metric: string; r: number }[];
}

export interface InsightsPayload {
  range: string;
  generated_at: ISODate;
  flags: MetricFlag[];
  insights: InsightCard[];
  patterns: InsightCard[];
}

export interface CoachObs { text: string; tone: "good" | "warn" | "bad" | "neutral"; kind: string; }
export interface CoachAction { text: string; priority: "high" | "medium" | "low"; }
export interface CoachRisk { text: string; severity: "high" | "medium" | "low"; }

export interface CoachPayload {
  headline: string; summary: string;
  observations: CoachObs[]; actions: CoachAction[]; risks: CoachRisk[];
  confidence: number; used_ai?: boolean; warning?: string;
  context?: Record<string, unknown>;
}

export interface GarminStatus {
  configured: boolean;
  connected?: boolean;
  status?: string;
  account?: string | null;
  email: string | null;
  message: string;
  last_synced_at?: string | null;
  last_sync_age_hours?: number | null;
  is_stale?: boolean;
  history_import?: HistoryImportJob | null;
}

export interface HistoryImportJob {
  id: number;
  status: "queued" | "running" | "completed" | "completed_with_errors" | "failed";
  days_requested: number;
  total_days: number;
  completed_days: number;
  synced_days: number;
  skipped_days: number;
  failed_days: number;
  progress_pct: number;
  current_date?: string | null;
  error?: string | null;
  started_at?: string | null;
  finished_at?: string | null;
}

export interface PolishResponse { text: string; original: string; used_ai: boolean; warning: string | null; }

export type BodyGoal = "maintain" | "lose_weight" | "gain_weight" | "gain_muscle" | "lose_fat";

export interface PlanningSettings {
  body_goal: BodyGoal;
  work_start: string | null;
  work_end: string | null;
  commute_minutes: number | null;
  preferred_wake: string | null;
  desired_sleep_hours: number;
  hidden_cards: string[];
  available_cards: string[];
}

export interface NutritionPlan {
  status: "ready" | "needs_weight" | string;
  title?: string;
  goal: BodyGoal;
  weight_kg?: number;
  protein_g: { low: number; high: number; midpoint: number } | null;
  energy_kcal: { estimate: number; bmr: number; activity_kcal: number; goal_adjustment: number } | null;
  today_activity?: { label: string; duration_minutes: number; types: string[] };
  confidence: "low" | "medium" | "high" | string;
  notes: string[];
}

export interface SleepSchedule {
  status: "ready" | "needs_history" | string;
  ideal_bedtime: string | null;
  ideal_wake_time: string | null;
  target_bedtime: string | null;
  wind_down_start: string | null;
  latest_practical_wake: string | null;
  sample_nights: number;
  confidence: "low" | "medium" | "high" | string;
  notes: string[];
}

export interface SleepExplorer {
  range_days: number;
  filters: Record<string, string | number | null>;
  points: Array<{ date: string; sleep_score: number | null; bedtime: string | null; wake_time: string | null; deep_minutes: number | null; rem_minutes: number | null; workout_types: string[]; workout_duration_minutes: number; workout_average_hr: number | null }>;
  summary: { nights: number; average_sleep_score: number | null; confidence: string };
}

export interface FitnessPrediction {
  distance_km: number;
  estimate_seconds: number | null;
  range_seconds: [number, number] | null;
  confidence: string;
}

export interface FitnessPredictions {
  window_days: number;
  sessions: Record<string, number>;
  running: FitnessPrediction[];
  cycling: FitnessPrediction[];
  scenario: { title: string; detail: string; confidence: string; improvement?: { window_days: number; change_pct: [number, number]; condition: string } | null; decline?: { window_days: number; change_pct: [number, number]; condition: string } | null };
  inputs?: { vo2max: number | null; mean_workout_hr: number | null; rpe: number | null };
  notes: string[];
}

// Legacy compat
export interface Ring {
  label: string; value: number; target: number; color: string;
}

export interface HealthMetric {
  name: string; value: number | null; unit: string | null;
  delta_7d: number | null; status: "good" | "warn" | "bad" | null;
}
