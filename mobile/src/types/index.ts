export type ISODate = string;
export type ISODateTime = string;

export interface Goal {
  id: number;
  date: ISODate;
  text: string;
  done: boolean;
  done_at: ISODateTime | null;
  queued: boolean;
  sort_order: number;
  created_at: ISODateTime;
  updated_at: ISODateTime;
}

export interface Streak {
  count: number;
  last_processed_date: ISODate | null;
}

export interface DayProgress {
  percent: number;
  phase: string;
  status: string;
  remaining_seconds: number;
  wake_iso: string;
  sleep_iso: string;
  now_iso: string;
}

export interface Ring {
  label: string;
  value: number;
  target: number;
  color: string;
}

export interface HealthMetric {
  name: string;
  value: number | null;
  unit: string | null;
  delta_7d: number | null;
  status: "good" | "warn" | "bad" | null;
}

export interface Dashboard {
  active_date: ISODate;
  day_progress: DayProgress;
  rings: Ring[];
  metrics: HealthMetric[];
  streak: number;
  goals_total: number;
  goals_completed: number;
  goals_queued: number;
}

export interface CoachPayload {
  summary: string;
  recommendations: {
    kind: string;
    title: string;
    body: string;
    tone: "good" | "warn" | "bad" | "neutral";
  }[];
  context: Record<string, number | string>;
}
