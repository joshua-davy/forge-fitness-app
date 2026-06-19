import { FormEvent, useEffect, useRef, useState } from "react";
import { AgeCard } from "@/components/ages/AgeCard";
import { DayProgressRing } from "@/components/day/DayProgressRing";
import { GoalTicker } from "@/components/goals/GoalTicker";
import { TodayGoalsCard } from "@/components/goals/TodayGoalsCard";
import { TomorrowGoalsCard } from "@/components/goals/TomorrowGoalsCard";
import { MetricCard } from "@/components/health/MetricCard";
import { MetricChart } from "@/components/health/MetricChart";
import { HealthRings } from "@/components/health/HealthRings";
import { RangeMarkerCard } from "@/components/health/RangeMarkerCard";
import { Header } from "@/components/layout/Header";
import { Onboarding } from "@/components/layout/Onboarding";
import { api } from "@/lib/api";
import { useCoach, useDashboard, useDayProgress, useGarminStatus, useGoals, useInsights } from "@/hooks/data";
import type { AuthUser, CoachPayload, Dashboard, InsightsPayload, MetricSeries, SpecialMetric } from "@/types";
import "./Dashboard.css";

type AppSection = "home" | "fitness" | "biology" | "sleep" | "focus" | "profile";
type MetricFilter = "all" | "poor" | "watch" | "good" | "missing";

export function DashboardScreen() {
  const [selectedDate, setSelectedDate] = useState(() => new Date().toISOString().slice(0, 10));
  const { data: dash, loading: dashLoading, refresh: refreshDash } = useDashboard(selectedDate);
  const { data: day } = useDayProgress();
  const { data: coach, error: coachError, refresh: refreshCoach } = useCoach();
  const { data: garmin } = useGarminStatus();
  const { data: insights } = useInsights(selectedDate);
  const goals = useGoals();

  const [syncing, setSyncing] = useState(false);
  const [syncMsg, setSyncMsg] = useState<string | null>(null);
  const [drillMetric, setDrillMetric] = useState<{ key: string; label: string; color: string; unit: string } | null>(null);
  const [bodyDraft, setBodyDraft] = useState({ weight: "", bodyFat: "", muscleMass: "" });
  const [bodyMsg, setBodyMsg] = useState<string | null>(null);
  const [profileDraft, setProfileDraft] = useState({ name: "", dateOfBirth: "", heightCm: "", weight: "", bodyFat: "", muscleMass: "" });
  const [profileDirty, setProfileDirty] = useState(false);
  const [profileMsg, setProfileMsg] = useState<string | null>(null);
  const [authUser, setAuthUser] = useState<AuthUser | null>(null);
  const [authDraft, setAuthDraft] = useState({ email: "", password: "", displayName: "" });
  const [authMsg, setAuthMsg] = useState<string | null>(null);
  const [section, setSection] = useState<AppSection>("home");
  const [metricFilter, setMetricFilter] = useState<MetricFilter>("all");
  const [fitnessSeries, setFitnessSeries] = useState<Record<string, MetricSeries | null>>({});
  const bootSynced = useRef(false);

  const syncToday = async () => {
    setSyncing(true); setSyncMsg(null);
    try {
      await api.syncGarmin();
      setSyncMsg("Synced ✓");
      refreshDash(); refreshCoach();
    } catch (e: unknown) {
      setSyncMsg(e instanceof Error ? e.message : "Sync failed");
    } finally {
      setSyncing(false);
      setTimeout(() => setSyncMsg(null), 4000);
    }
  };

  const noData = !dashLoading && dash && !dash.has_garmin_data;
  const m = dash?.metrics;
  const special = dash?.special_metrics ?? {};

  useEffect(() => {
    if (!m) return;
    setBodyDraft({
      weight: m.weight_kg ? String(m.weight_kg) : "",
      bodyFat: m.body_fat_pct ? String(m.body_fat_pct) : "",
      muscleMass: m.muscle_mass_kg ? String(m.muscle_mass_kg) : "",
    });
  }, [m?.weight_kg, m?.body_fat_pct, m?.muscle_mass_kg]);

  useEffect(() => {
    if (!dash || profileDirty) return;
    setProfileDraft({
      name: dash.profile?.name ?? "Forge Athlete",
      dateOfBirth: dash.profile?.date_of_birth ?? "",
      heightCm: dash.profile?.height_cm ? String(dash.profile.height_cm) : "",
      weight: m?.weight_kg ? String(m.weight_kg) : "",
      bodyFat: m?.body_fat_pct ? String(m.body_fat_pct) : "",
      muscleMass: m?.muscle_mass_kg ? String(m.muscle_mass_kg) : "",
    });
  }, [dash?.profile?.name, dash?.profile?.date_of_birth, dash?.profile?.height_cm, m?.weight_kg, m?.body_fat_pct, m?.muscle_mass_kg, profileDirty]);

  useEffect(() => {
    if (bootSynced.current || !garmin?.configured || syncing) return;
    if (selectedDate !== new Date().toISOString().slice(0, 10)) return;
    if (garmin.is_stale || !garmin.last_synced_at) {
      bootSynced.current = true;
      syncToday();
    }
  }, [garmin?.configured, garmin?.is_stale, garmin?.last_synced_at, selectedDate, syncing]);

  useEffect(() => {
    if (!localStorage.getItem("forge_auth_token")) return;
    api.authMe()
      .then((payload) => setAuthUser(payload.user))
      .catch(() => {
        localStorage.removeItem("forge_auth_token");
        setAuthUser(null);
      });
  }, []);

  useEffect(() => {
    if (section !== "fitness") return;
    let cancelled = false;
    Promise.all([
      api.metricSeries("cardio_load", "30d", selectedDate).catch(() => null),
      api.metricSeries("active_minutes", "30d", selectedDate).catch(() => null),
      api.metricSeries("vigorous_minutes", "30d", selectedDate).catch(() => null),
      api.metricSeries("steps", "30d", selectedDate).catch(() => null),
    ]).then(([cardioLoad, activeMinutes, vigorousMinutes, steps]) => {
      if (cancelled) return;
      setFitnessSeries({ cardioLoad, activeMinutes, vigorousMinutes, steps });
    });
    return () => { cancelled = true; };
  }, [section, selectedDate]);

  const drill = (key: string, label: string, color: string, unit: string) =>
    setDrillMetric({ key, label, color, unit });

  const saveBody = async (event: FormEvent) => {
    event.preventDefault();
    setBodyMsg(null);
    try {
      await api.saveBodyComposition({
        date: selectedDate,
        weight_kg: parseOptionalNumber(bodyDraft.weight),
        body_fat_pct: parseOptionalNumber(bodyDraft.bodyFat),
        muscle_mass_kg: parseOptionalNumber(bodyDraft.muscleMass),
      });
      setBodyMsg("Saved");
      refreshDash();
      refreshCoach();
    } catch (e: unknown) {
      setBodyMsg(e instanceof Error ? e.message : "Save failed");
    } finally {
      setTimeout(() => setBodyMsg(null), 3500);
    }
  };

  const saveProfile = async (event: FormEvent) => {
    event.preventDefault();
    setProfileMsg(null);
    try {
      await api.updateProfile({
        name: profileDraft.name.trim() || "Forge Athlete",
        date_of_birth: profileDraft.dateOfBirth || undefined,
        height_cm: parseOptionalNumber(profileDraft.heightCm) ?? undefined,
        weight_kg: parseOptionalNumber(profileDraft.weight) ?? undefined,
        body_fat_pct: parseOptionalNumber(profileDraft.bodyFat) ?? undefined,
        muscle_mass_kg: parseOptionalNumber(profileDraft.muscleMass) ?? undefined,
      });
      setProfileDirty(false);
      setProfileMsg("Profile saved");
      refreshDash();
      refreshCoach();
    } catch (e: unknown) {
      setProfileMsg(e instanceof Error ? e.message : "Profile save failed");
    } finally {
      setTimeout(() => setProfileMsg(null), 3500);
    }
  };

  const handleSignup = async (event: FormEvent) => {
    event.preventDefault();
    setAuthMsg(null);
    try {
      const payload = await api.authSignup({
        email: authDraft.email,
        password: authDraft.password,
        display_name: authDraft.displayName || profileDraft.name || "Forge Athlete",
      });
      localStorage.setItem("forge_auth_token", payload.token);
      setAuthUser(payload.user);
      setAuthMsg("Account created. This browser is signed in.");
    } catch (e: unknown) {
      setAuthMsg(e instanceof Error ? e.message : "Signup failed");
    }
  };

  const handleLogin = async (event: FormEvent) => {
    event.preventDefault();
    setAuthMsg(null);
    try {
      const payload = await api.authLogin({ email: authDraft.email, password: authDraft.password });
      localStorage.setItem("forge_auth_token", payload.token);
      setAuthUser(payload.user);
      setAuthMsg("Signed in.");
    } catch (e: unknown) {
      setAuthMsg(e instanceof Error ? e.message : "Login failed");
    }
  };

  const handleLogout = async () => {
    try {
      await api.authLogout();
    } catch {
      // Local token cleanup still matters if the server session already expired.
    }
    localStorage.removeItem("forge_auth_token");
    setAuthUser(null);
    setAuthMsg("Signed out.");
  };

  return (
    <main className="app">
      <Header
        date={dash?.active_date ?? selectedDate}
        onPreviousDay={() => setSelectedDate(shiftDate(selectedDate, -1))}
        onNextDay={() => setSelectedDate(shiftDate(selectedDate, 1))}
        onToday={() => setSelectedDate(new Date().toISOString().slice(0, 10))}
        nextDisabled={selectedDate >= new Date().toISOString().slice(0, 10)}
      />

      {/* Sync bar */}
      <div className="dash-syncbar">
        <div className="dash-syncbar__status">
          <span className={`dash-syncbar__dot ${garmin?.configured ? "dash-syncbar__dot--on" : ""}`} />
          <span className="meta">{garmin?.configured ? `Garmin connected · ${garmin.email}${syncFreshness(garmin.last_sync_age_hours)}` : "Garmin not configured"}</span>
        </div>
        <div className="dash-syncbar__right">
          {syncMsg && <span className="dash-syncbar__msg">{syncMsg}</span>}
          <button className="dash-syncbar__btn" onClick={syncToday} disabled={syncing || !garmin?.configured}>
            {syncing ? "Syncing…" : "↻ Sync Garmin"}
          </button>
        </div>
      </div>

      <nav className="dash-floatnav" aria-label="Forge sections">
        {[
          { key: "home", label: "Home" },
          { key: "fitness", label: "Fitness" },
          { key: "biology", label: "Biology" },
          { key: "sleep", label: "Sleep" },
          { key: "focus", label: "Focus" },
          { key: "profile", label: "Profile" },
        ].map((item) => (
          <button
            key={item.key}
            className={section === item.key ? "dash-floatnav__item dash-floatnav__item--active" : "dash-floatnav__item"}
            onClick={() => setSection(item.key as AppSection)}
            type="button"
          >
            {item.label}
          </button>
        ))}
      </nav>

      {noData && garmin !== null ? (
        <Onboarding garminConfigured={garmin?.configured ?? false} onSynced={refreshDash} />
      ) : (
        <>
          {/* Drill-down overlay */}
          {drillMetric && (
            <div className="dash-drill-backdrop" role="presentation" onClick={() => setDrillMetric(null)}>
              <div className="dash-drill card" role="dialog" aria-modal="true" onClick={(event) => event.stopPropagation()}>
              <div className="dash-drill__head">
                <span className="dash-drill__title">{drillMetric.label}</span>
                <button className="dash-drill__close" onClick={() => setDrillMetric(null)}>✕</button>
              </div>
              <MetricChart metric={drillMetric.key} label={drillMetric.label} color={drillMetric.color} unit={drillMetric.unit} date={selectedDate} />
              </div>
            </div>
          )}

          {/* Insights and flags */}
          {section === "home" && insights && (
            <section className="dash-section dash-intel">
              <div className="dash-intel__panel card">
                <div className="dash-intel__head">
                  <div>
                    <div className="card__label">Signals to watch</div>
                    <div className="dash-intel__sub">90-day trend analysis and metric flags.</div>
                  </div>
                  <span className="dash-intel__count">{insights.flags.length} flags</span>
                </div>
                <div className="dash-intel__list">
                  {(insights.flags.length ? insights.flags.slice(0, 3) : insights.insights.slice(0, 3)).map((item, index) => (
                    <button
                      key={`${item.metric}-${item.title}-${index}`}
                      className={`dash-intel__item ${"severity" in item ? `dash-intel__item--${item.severity}` : ""}`}
                      onClick={() => drill(item.metric, labelForMetric(item.metric), colorForMetric(item.metric), unitForMetric(item.metric))}
                    >
                      <strong>{item.title}</strong>
                      <span>{"detail" in item ? item.detail : item.summary}</span>
                    </button>
                  ))}
                </div>
              </div>
              <div className="dash-intel__panel card">
                <div className="dash-intel__head">
                  <div>
                    <div className="card__label">Patterns</div>
                    <div className="dash-intel__sub">Behaviour-linked insights from your history.</div>
                  </div>
                </div>
                <div className="dash-intel__list">
                  {insights.patterns.slice(0, 3).map((pattern) => (
                    <button
                      key={pattern.id ?? pattern.title}
                      className="dash-intel__item"
                      onClick={() => drill(pattern.metric, labelForMetric(pattern.metric), colorForMetric(pattern.metric), unitForMetric(pattern.metric))}
                    >
                      <strong>{pattern.title}</strong>
                      <span>{pattern.summary}</span>
                    </button>
                  ))}
                </div>
              </div>
            </section>
          )}

          {/* Age heroes */}
          {section === "home" && <section className="dash-section dash-ages">
            <AgeCard
              kind="fitness"
              age={dash?.fitness_age ?? null}
              actualAge={dash?.actual_age ?? 30}
              delta={dash?.fitness_age_delta ?? null}
              status={dash?.fitness_age_status ?? null}
              drivers={dash?.fitness_age_drivers ?? []}
              onClick={() => drill("fitness_age", "Fitness Age", "#6BE3A4", "yrs")}
            />
            <AgeCard
              kind="biological"
              age={dash?.biological_age ?? null}
              actualAge={dash?.actual_age ?? 30}
              delta={dash?.biological_age_delta ?? null}
              status={dash?.biological_age_status ?? null}
              drivers={dash?.biological_age_drivers ?? []}
              onClick={() => drill("biological_age", "Biological Age", "#8F7CFF", "yrs")}
            />
          </section>}

          {/* Rings */}
          {section === "home" && dash && <section className="dash-section"><HealthRings rings={dash.rings} /></section>}

          {/* Decision-first metrics */}
          {section === "home" && (
            <>
              <section className="dash-section">
                <SectionCoach data={coach} dashboard={dash} focus="home" loadError={coachError} onRefresh={refreshCoach} />
              </section>
              <MetricFilterBar value={metricFilter} onChange={setMetricFilter} />
              <section className="dash-section dash-ranges">
                {showMetric(metricFilter, scoreTone(m?.sleep_score)) && <RangeMarkerCard label="Sleep Score" value={m?.sleep_score} min={0} max={100} normalLow={75} normalHigh={100} mode="higher" help="Sleep quality and debt context." onClick={() => drill("sleep_score","Sleep Score","#8F7CFF","")} />}
                {showMetric(metricFilter, rhrTone(m?.rhr)) && <RangeMarkerCard label="Resting HR" value={m?.rhr} unit="bpm" min={40} max={95} normalLow={45} normalHigh={62} mode="lower" help={m?.rhr_baseline ? `Baseline ${m.rhr_baseline} bpm.` : "Lower usually means less strain."} onClick={() => drill("rhr","Resting HR","#FF6B6B","bpm")} />}
                {showMetric(metricFilter, hrvTone(m?.hrv, m?.hrv_baseline)) && <RangeMarkerCard label="HRV" value={m?.hrv} unit="ms" min={15} max={110} normalLow={m?.hrv_baseline ? m.hrv_baseline * 0.9 : 45} normalHigh={m?.hrv_baseline ? m.hrv_baseline * 1.25 : 85} mode="range" help={m?.hrv_baseline ? `Baseline ${m.hrv_baseline} ms.` : "Autonomic balance."} onClick={() => drill("hrv","HRV","#62E6D0","ms")} />}
                {showMetric(metricFilter, stressTone(m?.stress)) && <RangeMarkerCard label="Stress" value={m?.stress} min={0} max={100} normalLow={0} normalHigh={30} mode="lower" help="Lower daytime stress is better." onClick={() => drill("stress","Stress","#F2C063","")} />}
                {showMetric(metricFilter, spo2Tone(m?.spo2)) && <RangeMarkerCard label="SpO2" value={m?.spo2} unit="%" min={88} max={100} normalLow={95} normalHigh={100} mode="higher" help="Oxygen saturation." onClick={() => drill("spo2","SpO2","#5DADEC","%")} />}
                {showMetric(metricFilter, respirationTone(m?.respiration)) && <RangeMarkerCard label="Respiration" value={m?.respiration} unit="brpm" min={8} max={24} normalLow={11} normalHigh={17} mode="range" help="Stable is better than high variability." onClick={() => drill("respiration","Respiration","#62E6D0","brpm")} />}
                {showMetric(metricFilter, scoreTone(m?.body_battery)) && <RangeMarkerCard label="Body Battery" value={m?.body_battery} unit="%" min={0} max={100} normalLow={60} normalHigh={100} mode="higher" help="Energy reserve." onClick={() => drill("body_battery","Body Battery","#6BE3A4","%")} />}
                {showMetric(metricFilter, specialTone(special.physiological_anomaly_load)) && <RangeMarkerCard label="Physiology Stability" value={specialScore(special.physiological_anomaly_load)} unit="%" min={0} max={100} normalLow={75} normalHigh={100} mode="higher" help={specialSummary(special.physiological_anomaly_load, "Unusual HRV, RHR, stress, respiration, SpO2, and body battery signals.")} />}
                {showMetric(metricFilter, specialTone(special.training_gate)) && <RangeMarkerCard label="Training Gate" value={specialScore(special.training_gate)} unit="%" min={0} max={100} normalLow={58} normalHigh={100} mode="higher" help={specialSummary(special.training_gate, "Readiness gate for today's training intensity.")} />}
              </section>
            </>
          )}

          {section === "fitness" && (
            <>
              <section className="dash-section">
                <SectionCoach data={coach} dashboard={dash} focus="fitness" loadError={coachError} onRefresh={refreshCoach} />
              </section>
              <section className="dash-section dash-page-head card">
                <div>
                  <div className="card__label">Fitness cockpit</div>
                  <h2>Training load, aerobic capacity, and discipline freshness.</h2>
                  <p>Forge uses your current Garmin activity signals now, then can swap to sport-specific Garmin activity rows once we persist them per workout.</p>
                </div>
              </section>
              <section className="dash-section dash-ranges">
                <RangeMarkerCard label="VO2 Max" value={m?.vo2max} unit="ml/kg/min" min={25} max={70} normalLow={42} normalHigh={70} mode="higher" help="Latest Garmin-supported VO2 reading." onClick={() => drill("vo2max","VO2 Max","#FF9B5F","ml/kg/min")} />
                <RangeMarkerCard label="Fitness Age" value={dash?.fitness_age} unit="y" min={18} max={60} normalLow={18} normalHigh={dash?.actual_age ?? 30} mode="lower" help="Cardio fitness vs actual age." onClick={() => drill("fitness_age", "Fitness Age", "#6BE3A4", "yrs")} />
                <RangeMarkerCard label="Cardio Load" value={m?.cardio_load} min={0} max={300} normalLow={70} normalHigh={170} mode="target" help="Recent aerobic training dose." onClick={() => drill("cardio_load","Cardio Load","#FF9B5F","")} />
                <RangeMarkerCard label="Load Balance" value={m?.load_balance} min={0} max={2} normalLow={0.8} normalHigh={1.3} mode="target" help="Acute load vs longer baseline." onClick={() => drill("load_balance","Load Balance","#F2C063","")} />
                <RangeMarkerCard label="HR Recovery" value={m?.hr_recovery} unit="bpm" min={0} max={80} normalLow={25} normalHigh={80} mode="higher" help="Drop after hard work." onClick={() => drill("hr_recovery","HR Recovery","#62E6D0","bpm")} />
                <RangeMarkerCard label="Active Minutes" value={m?.active_minutes} unit="min" min={0} max={180} normalLow={25} normalHigh={90} mode="target" help="Daily movement dose." onClick={() => drill("active_minutes","Active Minutes","#5DADEC","min")} />
                <RangeMarkerCard label="Training Gate" value={specialScore(special.training_gate)} unit="%" min={0} max={100} normalLow={58} normalHigh={100} mode="higher" help={specialSummary(special.training_gate, "Today's training-intensity gate from recovery, sleep, HRV, RHR, and stress.")} />
                <RangeMarkerCard label="Resilience Ratio" value={specialScore(special.resilience_ratio)} unit="%" min={0} max={100} normalLow={70} normalHigh={100} mode="higher" help={specialSummary(special.resilience_ratio, "How well next-day recovery holds after strain.")} />
                <RangeMarkerCard label="Training Monotony" value={specialNumber(special.training_monotony)} min={0} max={3} normalLow={0.8} normalHigh={1.8} mode="target" help={specialSummary(special.training_monotony, "Load sameness across the last 7 days.")} />
              </section>
              <section className="dash-section dash-discipline-grid">
                {buildDisciplineCards(fitnessSeries).map((card) => (
                  <div key={card.title} className={`discipline-card card discipline-card--${card.tone}`}>
                    <div className="discipline-card__top">
                      <div>
                        <div className="card__label">{card.label}</div>
                        <h3>{card.title}</h3>
                      </div>
                      <span>{card.score}%</span>
                    </div>
                    <p>{card.summary}</p>
                    <div className="discipline-card__bar"><i style={{ width: `${card.score}%` }} /></div>
                    <small>{card.detail}</small>
                  </div>
                ))}
              </section>
            </>
          )}

          {section === "biology" && (
            <>
              <section className="dash-section">
                <SectionCoach data={coach} dashboard={dash} focus="biology" loadError={coachError} onRefresh={refreshCoach} />
              </section>
              <section className="dash-section dash-ages">
                <AgeCard
                  kind="fitness"
                  age={dash?.fitness_age ?? null}
                  actualAge={dash?.actual_age ?? 30}
                  delta={dash?.fitness_age_delta ?? null}
                  status={dash?.fitness_age_status ?? null}
                  drivers={dash?.fitness_age_drivers ?? []}
                  onClick={() => drill("fitness_age", "Fitness Age", "#6BE3A4", "yrs")}
                />
                <AgeCard
                  kind="biological"
                  age={dash?.biological_age ?? null}
                  actualAge={dash?.actual_age ?? 30}
                  delta={dash?.biological_age_delta ?? null}
                  status={dash?.biological_age_status ?? null}
                  drivers={dash?.biological_age_drivers ?? []}
                  onClick={() => drill("biological_age", "Biological Age", "#8F7CFF", "yrs")}
                />
              </section>
              <section className="dash-section dash-ranges">
                <RangeMarkerCard label="HRV" value={m?.hrv} unit="ms" min={15} max={110} normalLow={m?.hrv_baseline ? m.hrv_baseline * 0.9 : 45} normalHigh={m?.hrv_baseline ? m.hrv_baseline * 1.25 : 85} mode="range" help="Near baseline is usually stable." onClick={() => drill("hrv","HRV","#62E6D0","ms")} />
                <RangeMarkerCard label="Resting HR" value={m?.rhr} unit="bpm" min={40} max={95} normalLow={45} normalHigh={62} mode="lower" help="High values can indicate load or stress." onClick={() => drill("rhr","Resting HR","#FF6B6B","bpm")} />
                <RangeMarkerCard label="Stress" value={m?.stress} min={0} max={100} normalLow={0} normalHigh={30} mode="lower" help="Lower is better here." onClick={() => drill("stress","Stress","#F2C063","")} />
                <RangeMarkerCard label="Respiration" value={m?.respiration} unit="brpm" min={8} max={24} normalLow={11} normalHigh={17} mode="range" help="Stable range matters most." onClick={() => drill("respiration","Respiration","#62E6D0","brpm")} />
                <RangeMarkerCard label="SpO2" value={m?.spo2} unit="%" min={88} max={100} normalLow={95} normalHigh={100} mode="higher" help="Normal oxygen saturation." onClick={() => drill("spo2","SpO2","#5DADEC","%")} />
                <RangeMarkerCard label="Body Battery" value={m?.body_battery} unit="%" min={0} max={100} normalLow={60} normalHigh={100} mode="higher" help="Energy reserve." onClick={() => drill("body_battery","Body Battery","#6BE3A4","%")} />
                <RangeMarkerCard label="Weight" value={m?.weight_kg} unit="kg" min={50} max={110} normalLow={65} normalHigh={85} mode="range" help="Manual or Garmin body comp." onClick={() => drill("weight","Weight","#A7B0FF","kg")} />
                <RangeMarkerCard label="Body Fat" value={m?.body_fat_pct} unit="%" min={5} max={40} normalLow={10} normalHigh={22} mode="range" help="Enter manually if Garmin is missing it." onClick={() => drill("body_fat","Body Fat","#A7B0FF","%")} />
                <RangeMarkerCard label="Physiology Stability" value={specialScore(special.physiological_anomaly_load)} unit="%" min={0} max={100} normalLow={75} normalHigh={100} mode="higher" help={specialSummary(special.physiological_anomaly_load, "Multi-signal anomaly load versus baseline.")} />
                <RangeMarkerCard label="Respiratory Stability" value={specialScore(special.respiratory_stability_sleep)} unit="%" min={0} max={100} normalLow={78} normalHigh={100} mode="higher" help={specialSummary(special.respiratory_stability_sleep, "Breathing and SpO2 stability against recent baseline.")} />
              </section>
            </>
          )}

          {section === "sleep" && (
            <>
              <section className="dash-section">
                <SectionCoach data={coach} dashboard={dash} focus="sleep" loadError={coachError} onRefresh={refreshCoach} />
              </section>
              <section className="dash-section dash-ranges">
                <RangeMarkerCard label="Sleep Score" value={m?.sleep_score} min={0} max={100} normalLow={75} normalHigh={100} mode="higher" help="Overall sleep quality estimate." onClick={() => drill("sleep_score","Sleep Score","#8F7CFF","")} />
                <RangeMarkerCard label="Sleep Duration" value={m?.sleep_hours} unit="h" min={0} max={10} normalLow={7} normalHigh={9} mode="range" help="Healthy range beats simply more." onClick={() => drill("sleep_hours","Sleep Hours","#8F7CFF","h")} />
                <RangeMarkerCard label="Sleep Debt" value={m?.sleep_debt_hours} unit="h" min={0} max={5} normalLow={0} normalHigh={1} mode="lower" help="Lower debt improves readiness." onClick={() => drill("sleep_debt","Sleep Debt","#FF6B6B","h")} />
                <RangeMarkerCard label="Sleep Need" value={m?.sleep_need_hours} unit="h" min={6} max={10} normalLow={7} normalHigh={8.5} mode="range" help="Based on debt and recent strain." onClick={() => drill("sleep_need","Sleep Need","#8F7CFF","h")} />
                <RangeMarkerCard label="Deep Sleep" value={m?.deep_sleep_hours} unit="h" min={0} max={3} normalLow={1} normalHigh={2.2} mode="range" help="Restorative sleep stage." onClick={() => drill("deep_sleep","Deep Sleep","#8F7CFF","h")} />
                <RangeMarkerCard label="REM Sleep" value={m?.rem_sleep_hours} unit="h" min={0} max={3} normalLow={1.2} normalHigh={2.3} mode="range" help="Cognitive recovery stage." onClick={() => drill("rem_sleep","REM Sleep","#A7B0FF","h")} />
                <RangeMarkerCard label="Sleep Regularity" value={specialScore(special.sleep_regularity)} unit="%" min={0} max={100} normalLow={75} normalHigh={100} mode="higher" help={specialSummary(special.sleep_regularity, "Night-to-night bedtime and wake-time stability.")} />
                <RangeMarkerCard label="Social Jetlag" value={specialNumber(special.social_jetlag)} unit="h" min={0} max={3} normalLow={0} normalHigh={0.7} mode="lower" help={specialSummary(special.social_jetlag, "Weekday versus weekend midsleep drift.")} />
                <RangeMarkerCard label="Sleep Architecture" value={specialScore(special.sleep_architecture_confidence)} unit="%" min={0} max={100} normalLow={80} normalHigh={100} mode="higher" help={specialSummary(special.sleep_architecture_confidence, "Confidence that sleep-stage data is complete enough to interpret.")} />
                <RangeMarkerCard label="Respiratory Stability" value={specialScore(special.respiratory_stability_sleep)} unit="%" min={0} max={100} normalLow={78} normalHigh={100} mode="higher" help={specialSummary(special.respiratory_stability_sleep, "Breathing and oxygen stability during recovery.")} />
              </section>
              {insights && (
                <section className="dash-section dash-intel">
                  <div className="dash-intel__panel card">
                    <div className="dash-intel__head">
                      <div>
                        <div className="card__label">Sleep patterns</div>
                        <div className="dash-intel__sub">Bedtime, strain, stress, and next-day recovery links.</div>
                      </div>
                    </div>
                    <div className="dash-intel__list">
                      {insights.patterns.filter((pattern) => pattern.metric.includes("sleep") || pattern.title.toLowerCase().includes("sleep")).slice(0, 4).map((pattern) => (
                        <button key={pattern.id ?? pattern.title} className="dash-intel__item" onClick={() => drill(pattern.metric, labelForMetric(pattern.metric), colorForMetric(pattern.metric), unitForMetric(pattern.metric))}>
                          <strong>{pattern.title}</strong>
                          <span>{pattern.summary}</span>
                        </button>
                      ))}
                    </div>
                  </div>
                </section>
              )}
            </>
          )}

          {section === "focus" && (
            <FocusSection
              dashboard={dash}
              insights={insights}
              special={special}
              onDrill={drill}
            />
          )}

          {section === "profile" && (
            <ProfileSection
              dashboard={dash}
              garminEmail={garmin?.email ?? null}
              draft={profileDraft}
              onDraftChange={(next) => {
                setProfileDirty(true);
                setProfileDraft(next);
              }}
              onSave={saveProfile}
              message={profileMsg}
              authUser={authUser}
              authDraft={authDraft}
              onAuthDraftChange={setAuthDraft}
              onSignup={handleSignup}
              onLogin={handleLogin}
              onLogout={handleLogout}
              authMessage={authMsg}
            />
          )}

          {/* Expandable detail groups */}
          {(["sleep", "biology", "fitness"] as AppSection[]).includes(section) && <section className="dash-section dash-metric-groups">
            {section === "sleep" && <details className="dash-metric-group" open>
              <summary>
                <span>Sleep detail</span>
                <small>Stages, debt, and sleep need.</small>
              </summary>
              <div className="dash-metrics">
                <MetricCard label="Sleep" value={m?.sleep_hours ?? null} unit="h" onClick={() => drill("sleep_hours","Sleep Hours","#8F7CFF","h")} />
                <MetricCard label="Deep Sleep" value={m?.deep_sleep_hours ?? null} unit="h" onClick={() => drill("deep_sleep","Deep Sleep","#8F7CFF","h")} />
                <MetricCard label="REM Sleep" value={m?.rem_sleep_hours ?? null} unit="h" onClick={() => drill("rem_sleep","REM Sleep","#A7B0FF","h")} />
                <MetricCard label="Awake Time" value={m?.awake_time_hours ?? null} unit="h" onClick={() => drill("awake_time","Awake Time","#F2C063","h")} />
                <MetricCard label="Sleep Debt" value={m?.sleep_debt_hours ?? null} unit="h" status={m?.sleep_debt_hours ? (m.sleep_debt_hours < 1 ? "good" : m.sleep_debt_hours < 2 ? "warn" : "bad") : null} onClick={() => drill("sleep_debt","Sleep Debt","#FF6B6B","h")} />
                <MetricCard label="Sleep Need" value={m?.sleep_need_hours ?? null} unit="h" onClick={() => drill("sleep_need","Sleep Need","#8F7CFF","h")} />
              </div>
            </details>}

            {section === "biology" && <details className="dash-metric-group" open>
              <summary>
                <span>Heart and recovery</span>
                <small>Autonomic, oxygen, and heart response signals.</small>
              </summary>
              <div className="dash-metrics">
                <MetricCard label="Max HR" value={m?.max_hr ?? null} unit="bpm" onClick={() => drill("max_hr","Max HR","#FF6B6B","bpm")} />
                <MetricCard label="HR Recovery" value={m?.hr_recovery ?? null} unit="bpm" onClick={() => drill("hr_recovery","HR Recovery","#62E6D0","bpm")} />
                <MetricCard label="SpO2" value={m?.spo2 ?? null} unit="%" status={m?.spo2 ? (m.spo2 >= 97 ? "good" : m.spo2 >= 95 ? "warn" : "bad") : null} onClick={() => drill("spo2","SpO2","#5DADEC","%")} />
                <MetricCard label="Respiration" value={m?.respiration ?? null} unit="brpm" onClick={() => drill("respiration","Respiration","#62E6D0","brpm")} />
              </div>
            </details>}

            {section === "fitness" && <details className="dash-metric-group" open>
              <summary>
                <span>Fitness and load</span>
                <small>Training dose, movement, and cardio capacity.</small>
              </summary>
              <div className="dash-metrics">
                <MetricCard label="Target Strain" value={m?.target_strain ?? null} onClick={() => drill("target_strain","Target Strain","#F2C063","")} />
                <MetricCard label="VO2 Max" value={m?.vo2max ?? null} onClick={() => drill("vo2max","VO2 Max","#FF9B5F","ml/kg/min")} />
                <MetricCard label="Cardio Load" value={m?.cardio_load ?? null} onClick={() => drill("cardio_load","Cardio Load","#FF9B5F","")} />
                <MetricCard label="Load Balance" value={m?.load_balance ?? null} onClick={() => drill("load_balance","Load Balance","#F2C063","")} />
                <MetricCard label="Active Cal" value={m?.active_calories ?? null} unit="kcal" onClick={() => drill("active_calories","Active Calories","#F2C063","kcal")} />
                <MetricCard label="Active Min" value={m?.active_minutes ?? null} unit="min" onClick={() => drill("active_minutes","Active Minutes","#5DADEC","min")} />
                <MetricCard label="Moderate Min" value={m?.moderate_minutes ?? null} unit="min" onClick={() => drill("moderate_minutes","Moderate Minutes","#5DADEC","min")} />
                <MetricCard label="Vigorous Min" value={m?.vigorous_minutes ?? null} unit="min" onClick={() => drill("vigorous_minutes","Vigorous Minutes","#FF9B5F","min")} />
                <MetricCard label="Distance" value={m?.distance_km ?? null} unit="km" onClick={() => drill("distance","Distance","#5DADEC","km")} />
                <MetricCard label="Floors" value={m?.floors ?? null} onClick={() => drill("floors","Floors","#5DADEC","")} />
              </div>
            </details>}

            {section === "biology" && <details className="dash-metric-group" open>
              <summary>
                <span>Body and biology</span>
                <small>Body composition and long-term baseline markers.</small>
              </summary>
              <div className="dash-metrics">
                <MetricCard label="Weight" value={m?.weight_kg ?? null} unit="kg" onClick={() => drill("weight","Weight","#A7B0FF","kg")} />
                <MetricCard label="Body Fat" value={m?.body_fat_pct ?? null} unit="%" onClick={() => drill("body_fat","Body Fat","#A7B0FF","%")} />
                <MetricCard label="Muscle Mass" value={m?.muscle_mass_kg ?? null} unit="kg" onClick={() => drill("muscle_mass","Muscle Mass","#A7B0FF","kg")} />
                <MetricCard label="BMI" value={m?.bmi ?? null} onClick={() => drill("bmi","BMI","#A7B0FF","")} />
              </div>
              <form className="dash-body-form" onSubmit={saveBody}>
                <div>
                  <span>Manual body update</span>
                  <small>Saved to this date and used in body composition trends.</small>
                </div>
                <label>
                  Weight kg
                  <input inputMode="decimal" value={bodyDraft.weight} onChange={(event) => setBodyDraft((prev) => ({ ...prev, weight: event.target.value }))} placeholder="78" />
                </label>
                <label>
                  Body fat %
                  <input inputMode="decimal" value={bodyDraft.bodyFat} onChange={(event) => setBodyDraft((prev) => ({ ...prev, bodyFat: event.target.value }))} placeholder="15" />
                </label>
                <label>
                  Muscle kg
                  <input inputMode="decimal" value={bodyDraft.muscleMass} onChange={(event) => setBodyDraft((prev) => ({ ...prev, muscleMass: event.target.value }))} placeholder="62" />
                </label>
                <button type="submit">Save body data</button>
                {bodyMsg && <em>{bodyMsg}</em>}
              </form>
            </details>}
          </section>}

          {/* Goal ticker */}
          {section === "home" && <section className="dash-section">
            <GoalTicker goals={goals.today} />
          </section>}

          {/* Command centre */}
          {section === "home" && <section className="dash-section dash-cmd">
            <div className="card dash-day">
              <div className="card__label">Day progress</div>
              <DayProgressRing data={day} />
            </div>
            <TodayGoalsCard
              goals={goals.today} streak={goals.streak}
              onCreate={goals.create} onUpdate={goals.update}
              onDelete={goals.remove} onReorder={goals.reorder}
              onPushRemaining={goals.pushRemaining}
            />
            <TomorrowGoalsCard
              goals={goals.tomorrow}
              onCreate={goals.create} onUpdate={goals.update}
              onDelete={goals.remove} onReorder={goals.reorder}
            />
          </section>}
        </>
      )}

      <footer className="dash-foot">
        <span>FORGE · v0.2.0</span>
        <span>Built on Garmin Connect · <a href="http://localhost:8000/docs" target="_blank" rel="noreferrer" style={{color:"inherit"}}>API docs</a></span>
      </footer>
    </main>
  );
}

function MetricFilterBar({ value, onChange }: { value: MetricFilter; onChange: (next: MetricFilter) => void }) {
  const items: { key: MetricFilter; label: string }[] = [
    { key: "all", label: "All" },
    { key: "poor", label: "Poor" },
    { key: "watch", label: "Watch" },
    { key: "good", label: "Good" },
    { key: "missing", label: "Missing" },
  ];
  return (
    <section className="dash-section metric-filter" aria-label="Metric status filter">
      <span>Filter markers</span>
      <div>
        {items.map((item) => (
          <button
            key={item.key}
            type="button"
            className={value === item.key ? "metric-filter__btn metric-filter__btn--active" : "metric-filter__btn"}
            onClick={() => onChange(item.key)}
          >
            {item.label}
          </button>
        ))}
      </div>
    </section>
  );
}

function FocusSection({
  dashboard,
  insights,
  special,
  onDrill,
}: {
  dashboard: Dashboard | null;
  insights: InsightsPayload | null;
  special: Record<string, SpecialMetric>;
  onDrill: (key: string, label: string, color: string, unit: string) => void;
}) {
  const items = focusMetrics(dashboard, special);
  const poor = items.filter((item) => item.tone === "bad").slice(0, 5);
  const watch = items.filter((item) => item.tone === "warn" || item.tone === "low").slice(0, 5);
  const good = items.filter((item) => item.tone === "good").slice(0, 5);
  const trendWatch = focusTrendItems(insights).slice(0, 5);
  const improvements = (insights?.insights ?? [])
    .filter((item) => item.summary.toLowerCase().includes("improving") || item.summary.toLowerCase().includes("stable"))
    .slice(0, 3);

  return (
    <>
      <section className="dash-section dash-page-head card">
        <div>
          <div className="card__label">Focus</div>
          <h2>What needs work, what only needs a nudge, and what is already working.</h2>
          <p>Forge ranks focus areas by status and actionability so the dashboard becomes a plan, not a wall of metrics.</p>
        </div>
      </section>

      <section className="dash-section focus-grid">
        <FocusColumn title="Priority focus" subtitle="Poor markers with clear next actions." items={poor} empty="No poor markers in the current view." onDrill={onDrill} />
        <FocusColumn title="Small improvements" subtitle="Close enough to fix with small changes." items={watch} empty="No watch markers right now." onDrill={onDrill} />
        <FocusColumn title="Strong points" subtitle="Signals currently working in your favour." items={good} empty="Forge needs more data to identify strong points." onDrill={onDrill} />
      </section>

      <section className="dash-section dash-intel">
        <div className="dash-intel__panel card">
          <div className="dash-intel__head">
            <div>
              <div className="card__label">Trend watchlist</div>
              <div className="dash-intel__sub">Signals changing enough to deserve attention this range.</div>
            </div>
          </div>
          <div className="dash-intel__list">
            {trendWatch.length ? trendWatch.map((item) => (
              <button
                key={`${item.metric}-${item.title}`}
                className={`dash-intel__item dash-intel__item--${item.severity}`}
                onClick={() => onDrill(item.metric, labelForMetric(item.metric), colorForMetric(item.metric), unitForMetric(item.metric))}
              >
                <strong>{item.title}</strong>
                <span>{item.summary}</span>
              </button>
            )) : (
              <div className="dash-intel__item">
                <strong>No major trend shifts</strong>
                <span>Forge is not seeing a high-priority trend change in the current 90-day range.</span>
              </div>
            )}
          </div>
        </div>
        <div className="dash-intel__panel card">
          <div className="dash-intel__head">
            <div>
              <div className="card__label">Past focus signals</div>
              <div className="dash-intel__sub">Trend-based signs that a previous weak area is stabilising or improving.</div>
            </div>
          </div>
          <div className="dash-intel__list">
            {improvements.length ? improvements.map((item) => (
              <button
                key={`${item.metric}-${item.title}`}
                className="dash-intel__item"
                onClick={() => onDrill(item.metric, labelForMetric(item.metric), colorForMetric(item.metric), unitForMetric(item.metric))}
              >
                <strong>{item.title}</strong>
                <span>{item.summary}</span>
              </button>
            )) : (
              <div className="dash-intel__item">
                <strong>No completed focus history yet</strong>
                <span>Once a poor or watch marker improves over a range, Forge will show it here with the metric and context.</span>
              </div>
            )}
          </div>
        </div>
        <div className="dash-intel__panel card">
          <div className="dash-intel__head">
            <div>
              <div className="card__label">Correlation note</div>
              <div className="dash-intel__sub">How to read r-values in the app.</div>
            </div>
          </div>
          <p className="focus-note">
            r is a correlation coefficient from -1 to +1. r=0.47 means a moderate positive relationship: when one metric tends to rise, the other tends to rise too. It is not proof that one causes the other.
          </p>
        </div>
      </section>
    </>
  );
}

function focusTrendItems(insights: InsightsPayload | null) {
  if (!insights) return [];
  const fromFlags = insights.flags.map((flag) => ({
    metric: flag.metric,
    title: flag.title,
    summary: flag.detail,
    severity: flag.severity === "alert" ? "alert" : flag.severity === "watch" ? "watch" : "info",
  }));
  const fromInsights = insights.insights
    .filter((item) => {
      const text = `${item.title} ${item.summary}`.toLowerCase();
      return text.includes("declining") || text.includes("outside target") || text.includes("below target") || text.includes("above target");
    })
    .map((item) => ({
      metric: item.metric,
      title: item.title,
      summary: item.summary,
      severity: item.summary.toLowerCase().includes("outside") || item.summary.toLowerCase().includes("declining") ? "watch" : "info",
    }));
  const seen = new Set<string>();
  return [...fromFlags, ...fromInsights].filter((item) => {
    const key = `${item.metric}:${item.title}`;
    if (seen.has(key)) return false;
    seen.add(key);
    return true;
  });
}

function FocusColumn({
  title,
  subtitle,
  items,
  empty,
  onDrill,
}: {
  title: string;
  subtitle: string;
  items: FocusMetric[];
  empty: string;
  onDrill: (key: string, label: string, color: string, unit: string) => void;
}) {
  return (
    <div className="focus-column card">
      <div className="card__label">{title}</div>
      <p>{subtitle}</p>
      <div className="focus-list">
        {items.length ? items.map((item) => (
          <button
            key={item.key}
            type="button"
            className={`focus-item focus-item--${item.tone}`}
            onClick={() => onDrill(item.metricKey, item.label, colorForMetric(item.metricKey), item.unit)}
          >
            <span>
              <strong>{item.label}</strong>
              <em>{item.why}</em>
            </span>
            <b>{item.value}</b>
            <small>{item.action}</small>
          </button>
        )) : (
          <div className="focus-empty">{empty}</div>
        )}
      </div>
    </div>
  );
}

function ProfileSection({
  dashboard,
  garminEmail,
  draft,
  onDraftChange,
  onSave,
  message,
  authUser,
  authDraft,
  onAuthDraftChange,
  onSignup,
  onLogin,
  onLogout,
  authMessage,
}: {
  dashboard: Dashboard | null;
  garminEmail: string | null;
  draft: { name: string; dateOfBirth: string; heightCm: string; weight: string; bodyFat: string; muscleMass: string };
  onDraftChange: (next: { name: string; dateOfBirth: string; heightCm: string; weight: string; bodyFat: string; muscleMass: string }) => void;
  onSave: (event: FormEvent) => void;
  message: string | null;
  authUser: AuthUser | null;
  authDraft: { email: string; password: string; displayName: string };
  onAuthDraftChange: (next: { email: string; password: string; displayName: string }) => void;
  onSignup: (event: FormEvent) => void;
  onLogin: (event: FormEvent) => void;
  onLogout: () => void;
  authMessage: string | null;
}) {
  const profile = profileSnapshot(dashboard, garminEmail);
  const patchDraft = (patch: Partial<typeof draft>) => onDraftChange({ ...draft, ...patch });
  const patchAuth = (patch: Partial<typeof authDraft>) => onAuthDraftChange({ ...authDraft, ...patch });
  return (
    <>
      <section className="dash-section profile-hero card">
        <div className="profile-card-preview" id="forge-profile-card">
          <div className="profile-card-preview__head">
            <div>
              <span>Forge profile</span>
              <h2>{profile.name}</h2>
            </div>
            <strong>{profile.age}</strong>
          </div>
          <div className="profile-card-preview__grid">
            {profile.metrics.map((item) => (
              <div key={item.label}>
                <span>{item.label}</span>
                <strong>{item.value}</strong>
              </div>
            ))}
          </div>
        </div>
        <div className="profile-hero__copy">
          <div className="card__label">Profile base</div>
          <h2>Your identity and baseline metrics.</h2>
          <p>These values anchor age estimates, body composition context, health ranges, and future account profiles.</p>
          <button type="button" onClick={() => exportProfileImage(dashboard, garminEmail)}>Export profile image</button>
        </div>
      </section>

      <section className="dash-section profile-grid">
        {profile.details.map((item) => (
          <div key={item.label} className="profile-detail card">
            <span>{item.label}</span>
            <strong>{item.value}</strong>
            <small>{item.help}</small>
          </div>
        ))}
      </section>

      <section className="dash-section profile-edit card">
        <div>
          <div className="card__label">Edit profile</div>
          <h2>Update baseline details.</h2>
          <p>Name, DOB, and height are profile fields. Weight, body fat, and muscle mass are saved into today's body-composition snapshot so trends keep working.</p>
        </div>
        <form onSubmit={onSave}>
          <label>
            Name
            <input value={draft.name} onChange={(event) => patchDraft({ name: event.target.value })} placeholder="Your name" />
          </label>
          <label>
            Date of birth
            <input type="date" value={draft.dateOfBirth} onChange={(event) => patchDraft({ dateOfBirth: event.target.value })} />
          </label>
          <label>
            Height cm
            <input inputMode="decimal" value={draft.heightCm} onChange={(event) => patchDraft({ heightCm: event.target.value })} placeholder="180" />
          </label>
          <label>
            Weight kg
            <input inputMode="decimal" value={draft.weight} onChange={(event) => patchDraft({ weight: event.target.value })} placeholder="73" />
          </label>
          <label>
            Body fat %
            <input inputMode="decimal" value={draft.bodyFat} onChange={(event) => patchDraft({ bodyFat: event.target.value })} placeholder="15" />
          </label>
          <label>
            Muscle kg
            <input inputMode="decimal" value={draft.muscleMass} onChange={(event) => patchDraft({ muscleMass: event.target.value })} placeholder="66" />
          </label>
          <button type="submit">Save profile</button>
          {message && <em>{message}</em>}
        </form>
      </section>

      <section className="dash-section account-panel card">
        <div>
          <div className="card__label">Account foundation</div>
          <h2>{authUser ? "Signed in account." : "Create or connect a Forge account."}</h2>
          <p>
            This is the first production step toward secure profiles, per-user Garmin/Apple Health connections, and private metric storage.
            The current dashboard remains local-single-user until metric tables are migrated to user scope.
          </p>
        </div>
        {authUser ? (
          <div className="account-panel__session">
            <span>Signed in as</span>
            <strong>{authUser.display_name}</strong>
            <small>{authUser.email}</small>
            <button type="button" onClick={onLogout}>Sign out</button>
          </div>
        ) : (
          <div className="account-panel__forms">
            <form onSubmit={onSignup}>
              <h3>Create account</h3>
              <label>
                Email
                <input value={authDraft.email} onChange={(event) => patchAuth({ email: event.target.value })} placeholder="you@example.com" />
              </label>
              <label>
                Password
                <input type="password" value={authDraft.password} onChange={(event) => patchAuth({ password: event.target.value })} placeholder="10+ characters" />
              </label>
              <label>
                Display name
                <input value={authDraft.displayName} onChange={(event) => patchAuth({ displayName: event.target.value })} placeholder={profile.name} />
              </label>
              <button type="submit">Create account</button>
            </form>
            <form onSubmit={onLogin}>
              <h3>Sign in</h3>
              <label>
                Email
                <input value={authDraft.email} onChange={(event) => patchAuth({ email: event.target.value })} placeholder="you@example.com" />
              </label>
              <label>
                Password
                <input type="password" value={authDraft.password} onChange={(event) => patchAuth({ password: event.target.value })} placeholder="Password" />
              </label>
              <button type="submit">Sign in</button>
            </form>
          </div>
        )}
        {authMessage && <em>{authMessage}</em>}
      </section>
    </>
  );
}

function SpecialMetricCard({ metric }: { metric: SpecialMetric | undefined }) {
  if (!metric) return null;
  const value = metric.value !== null && metric.value !== undefined
    ? `${metric.value}${typeof metric.value === "number" && metric.unit ? ` ${metric.unit}` : ""}`
    : metric.score !== null
      ? `${metric.score}%`
      : "Not ready";
  return (
    <div className={`special-card card special-card--${metric.tone}`}>
      <div className="special-card__top">
        <div>
          <div className="card__label">{metric.data_quality}</div>
          <h3>{metric.label}</h3>
        </div>
        <span>{value}</span>
      </div>
      <p>{metric.summary}</p>
      {metric.score !== null && (
        <div className="special-card__bar">
          <i style={{ width: `${Math.min(100, Math.max(0, metric.score))}%` }} />
        </div>
      )}
      <small>{metric.details[0] ?? metric.inputs.join(", ")}</small>
    </div>
  );
}

function SectionCoach({
  data,
  dashboard,
  focus,
  onRefresh,
  loadError,
}: {
  data: CoachPayload | null;
  dashboard: Dashboard | null;
  focus: AppSection;
  onRefresh?: () => void;
  loadError?: Error | null;
}) {
  const title = focus === "home" ? "Today coach" : `${focus[0].toUpperCase()}${focus.slice(1)} coach`;
  if (!data) {
    return (
      <div className="section-coach card">
        <div className="card__label">{title}</div>
        <p>{loadError ? `Coach failed to load: ${loadError.message}` : "Reading your current signals..."}</p>
        {loadError && <button onClick={onRefresh}>Retry</button>}
      </div>
    );
  }

  const keywords = coachKeywords(focus);
  const matches = (text: string) => keywords.some((word) => text.toLowerCase().includes(word));
  const pageBrief = pageCoachBrief(focus, dashboard, data);
  const observations = data.observations.filter((item) => matches(`${item.kind} ${item.text}`)).slice(0, 2);
  const actions = data.actions.filter((item) => matches(item.text)).slice(0, 2);
  const shownObservations = pageBrief.observations.length ? pageBrief.observations : observations;
  const shownActions = pageBrief.actions.length ? pageBrief.actions : actions;

  return (
    <div className="section-coach card">
      <div className="section-coach__head">
        <div>
          <div className="card__label">{title}</div>
          <h2>{pageBrief.headline}</h2>
        </div>
        <button onClick={onRefresh}>Refresh</button>
      </div>
      <div className="section-coach__grid">
        <div>
          <span className="section-coach__label">Observations</span>
          {shownObservations.map((item, index) => (
            <p key={`${item.text}-${index}`} className={`section-coach__point section-coach__point--${item.tone}`}>
              {item.text}
            </p>
          ))}
        </div>
        <div>
          <span className="section-coach__label">Actions</span>
          {shownActions.map((item, index) => (
            <p key={`${item.text}-${index}`} className={`section-coach__action section-coach__action--${item.priority}`}>
              {item.text}
            </p>
          ))}
        </div>
      </div>
    </div>
  );
}

function coachKeywords(focus: AppSection) {
  if (focus === "fitness") return ["strain", "training", "cardio", "vo2", "load", "active", "steps", "fitness", "exercise", "session"];
  if (focus === "biology") return ["hrv", "rhr", "stress", "recovery", "readiness", "spo2", "respiration", "body", "biological"];
  if (focus === "sleep") return ["sleep", "bed", "rem", "deep", "debt", "wake", "night"];
  return ["sleep", "recovery", "readiness", "strain", "stress", "body", "training"];
}

function pageCoachBrief(focus: AppSection, dash: Dashboard | null, coach: CoachPayload) {
  const m = dash?.metrics;
  if (focus === "focus") {
    return {
      headline: "Focus is ranked by current risk and actionability.",
      observations: [
        { text: m?.recovery !== null && m?.recovery !== undefined ? `Recovery is ${m.recovery}/100; this anchors today's training ceiling.` : "Recovery is missing for this day.", tone: scoreTone(m?.recovery) ?? "neutral" },
        { text: m?.sleep_debt_hours !== null && m?.sleep_debt_hours !== undefined ? `Sleep debt is ${m.sleep_debt_hours}h; lower is better for readiness.` : "Sleep debt is missing for this day.", tone: m?.sleep_debt_hours !== null && m?.sleep_debt_hours !== undefined ? (m.sleep_debt_hours < 1 ? "good" : m.sleep_debt_hours < 2 ? "warn" : "bad") : "neutral" },
      ],
      actions: [
        { text: "Start with the priority focus column.", priority: "high" },
        { text: "Keep strong-point habits stable.", priority: "low" },
      ],
    };
  }
  if (focus === "fitness") {
    const load = m?.cardio_load ?? null;
    const vo2 = m?.vo2max ?? null;
    const hrr = m?.hr_recovery ?? null;
    return {
      headline: load !== null
        ? `Fitness load is ${load > 170 ? "high" : load >= 70 ? "in range" : "light"} today.`
        : "Fitness signals are limited today.",
      observations: [
        { text: vo2 !== null ? `VO2 Max is ${vo2}, which is your current aerobic capacity anchor.` : "VO2 Max is not available for this date.", tone: vo2 !== null && vo2 >= 50 ? "good" : "neutral" },
        { text: hrr !== null ? `Heart-rate recovery is ${hrr} bpm from the latest qualifying workout.` : "HR recovery needs a qualifying workout with usable heart-rate samples.", tone: hrr !== null && hrr >= 25 ? "good" : hrr !== null ? "warn" : "neutral" },
      ],
      actions: [
        { text: (m?.recovery ?? 0) < 50 ? "Keep training easy until recovery improves." : "Aim for controlled aerobic work if time allows.", priority: (m?.recovery ?? 0) < 50 ? "high" : "medium" },
        { text: "Use the freshness cards to decide which discipline needs attention.", priority: "low" },
      ],
    };
  }
  if (focus === "biology") {
    return {
      headline: `Biology is ${biologyHeadline(m?.stress, m?.hrv, m?.hrv_baseline)}.`,
      observations: [
        { text: m?.hrv && m?.hrv_baseline ? `HRV is ${m.hrv} ms versus a ${m.hrv_baseline} ms baseline.` : "HRV baseline context is limited today.", tone: hrvTone(m?.hrv, m?.hrv_baseline) ?? "neutral" },
        { text: m?.stress !== null && m?.stress !== undefined ? `Stress is ${m.stress}; lower is better for this marker.` : "Stress is missing for this day.", tone: m?.stress !== null && m?.stress !== undefined ? (m.stress < 30 ? "good" : m.stress < 55 ? "warn" : "bad") : "neutral" },
      ],
      actions: [
        { text: (m?.stress ?? 0) > 45 ? "Keep the evening low stimulation." : "Maintain the current recovery routine.", priority: (m?.stress ?? 0) > 45 ? "medium" : "low" },
        { text: (m?.spo2 ?? 100) < 95 ? "Watch SpO2 trend before hard training." : "No oxygen flag from this reading.", priority: (m?.spo2 ?? 100) < 95 ? "high" : "low" },
      ],
    };
  }
  if (focus === "sleep") {
    return {
      headline: m?.sleep_debt_hours && m.sleep_debt_hours > 2
        ? `Sleep debt is elevated at ${m.sleep_debt_hours}h.`
        : "Sleep pressure is controlled.",
      observations: [
        { text: m?.sleep_score !== null && m?.sleep_score !== undefined ? `Sleep Score is ${m.sleep_score}; aim for 75+ for a strong night.` : "Sleep score is missing for this day.", tone: scoreTone(m?.sleep_score) ?? "neutral" },
        { text: m?.sleep_hours ? `Total sleep was ${m.sleep_hours}h against a 7-9h healthy range.` : "Sleep duration is missing for this day.", tone: m?.sleep_hours ? (m.sleep_hours >= 7 && m.sleep_hours <= 9 ? "good" : "warn") : "neutral" },
      ],
      actions: [
        { text: m?.sleep_debt_hours && m.sleep_debt_hours > 2 ? "Move wind-down 30 minutes earlier tonight." : "Keep bedtime consistent tonight.", priority: m?.sleep_debt_hours && m.sleep_debt_hours > 2 ? "high" : "low" },
        { text: "Avoid late intensity if sleep quality is the priority.", priority: "medium" },
      ],
    };
  }
  return {
    headline: coach.headline,
    observations: coach.observations.slice(0, 2),
    actions: coach.actions.slice(0, 2),
  };
}

interface FocusMetric {
  key: string;
  metricKey: string;
  label: string;
  value: string;
  unit: string;
  tone: "good" | "warn" | "bad" | "low" | "neutral";
  why: string;
  action: string;
}

function focusMetrics(dashboard: Dashboard | null, special: Record<string, SpecialMetric>): FocusMetric[] {
  const m = dashboard?.metrics;
  return [
    focusMetric("recovery", "Recovery", m?.recovery, "", scoreTone(m?.recovery), "Recovery controls training ceiling.", "Avoid intensity below 50; build back through sleep and easy movement."),
    focusMetric("readiness", "Readiness", m?.readiness, "", scoreTone(m?.readiness), "Readiness combines recovery and load balance.", "Use it to choose rest, easy, or moderate training."),
    focusMetric("sleep_score", "Sleep Score", m?.sleep_score, "", scoreTone(m?.sleep_score), "Sleep quality is a main recovery lever.", "Protect bedtime and reduce late intensity when this is low."),
    focusMetric("sleep_debt", "Sleep Debt", m?.sleep_debt_hours, "h", sleepDebtTone(m?.sleep_debt_hours), "Sleep debt increases recovery pressure.", "Move wind-down earlier until debt is under 1 hour."),
    focusMetric("hrv", "HRV", m?.hrv, "ms", hrvTone(m?.hrv, m?.hrv_baseline), "HRV shows autonomic recovery versus baseline.", "Keep strain easy when HRV is materially below baseline."),
    focusMetric("rhr", "Resting HR", m?.rhr, "bpm", rhrTone(m?.rhr), "RHR elevation can show stress, heat, illness, or load.", "Pair high RHR with lower intensity and hydration."),
    focusMetric("stress", "Stress", m?.stress, "", stressTone(m?.stress), "Lower stress supports sleep and HRV.", "Use a low-stimulation evening if stress is elevated."),
    focusMetric("spo2", "SpO2", m?.spo2, "%", spo2Tone(m?.spo2), "Oxygen saturation is a stability marker.", "Watch the trend if this stays below 95%."),
    focusMetric("respiration", "Respiration", m?.respiration, "brpm", respirationTone(m?.respiration), "Stable breathing is better than upward drift.", "Check sleep, illness, heat, and stress context if elevated."),
    focusMetric("body_battery", "Body Battery", m?.body_battery, "%", scoreTone(m?.body_battery), "Body Battery reflects available reserve.", "Keep the day light when reserve is low."),
    specialFocusMetric("training_gate", "readiness", special.training_gate, "Training Gate", "The gate turns physiology into an intensity decision.", "Follow the gate before choosing workout intensity."),
    specialFocusMetric("physiological_anomaly_load", "hrv", special.physiological_anomaly_load, "Physiology Stability", "This flags unusual multi-signal physiology.", "Inspect the top drivers before training hard."),
    specialFocusMetric("sleep_regularity", "sleep_score", special.sleep_regularity, "Sleep Regularity", "Regular timing improves sleep reliability.", "Keep bedtime and wake time inside a tighter window."),
    specialFocusMetric("resilience_ratio", "recovery", special.resilience_ratio, "Resilience Ratio", "This shows how recovery responds after strain.", "Space hard sessions if recovery falls after load."),
  ].filter((item) => item.tone !== "neutral" || item.value !== "No data");
}

function focusMetric(
  key: string,
  label: string,
  value: number | null | undefined,
  unit: string,
  tone: FocusMetric["tone"] | null,
  why: string,
  action: string,
): FocusMetric {
  return {
    key,
    metricKey: key,
    label,
    value: value !== null && value !== undefined ? `${formatFocusValue(value)}${unit ? ` ${unit}` : ""}` : "No data",
    unit,
    tone: tone ?? "neutral",
    why,
    action,
  };
}

function specialFocusMetric(
  key: string,
  metricKey: string,
  metric: SpecialMetric | undefined,
  label: string,
  why: string,
  action: string,
): FocusMetric {
  const raw = metric?.value ?? metric?.score ?? null;
  const value = raw !== null && raw !== undefined
    ? `${raw}${typeof raw === "number" && metric?.unit ? ` ${metric.unit}` : ""}`
    : "No data";
  return {
    key,
    metricKey,
    label,
    value,
    unit: metric?.unit ?? "",
    tone: specialTone(metric) ?? "neutral",
    why,
    action,
  };
}

function profileSnapshot(dashboard: Dashboard | null, garminEmail: string | null) {
  const name = dashboard?.profile?.name || garminEmail?.split("@")[0]?.replace(/[._-]/g, " ") || "Forge Athlete";
  const height = dashboard?.profile?.height_cm ?? 180;
  const m = dashboard?.metrics;
  const weight = m?.weight_kg ?? null;
  const bmi = m?.bmi ?? (weight ? weight / ((height / 100) ** 2) : null);
  const profileMetrics = [
    { label: "Fitness age", value: dashboard?.fitness_age ? `${dashboard.fitness_age.toFixed(1)}y` : "No data" },
    { label: "Bio age", value: dashboard?.biological_age ? `${dashboard.biological_age.toFixed(1)}y` : "No data" },
    { label: "Recovery", value: m?.recovery !== null && m?.recovery !== undefined ? `${Math.round(m.recovery)}/100` : "No data" },
    { label: "Sleep", value: m?.sleep_score !== null && m?.sleep_score !== undefined ? `${Math.round(m.sleep_score)}/100` : "No data" },
    { label: "HRV", value: m?.hrv ? `${m.hrv} ms` : "No data" },
    { label: "RHR", value: m?.rhr ? `${m.rhr} bpm` : "No data" },
  ];
  const details = [
    { label: "Name", value: titleCase(name), help: "Display name for profile exports." },
    { label: "Date of birth", value: dashboard?.profile?.date_of_birth ?? "Not set", help: "Used for age-based ranges and age scores." },
    { label: "Actual age", value: dashboard?.actual_age ? `${dashboard.actual_age.toFixed(1)} years` : "No data", help: "Calculated from DOB." },
    { label: "Height", value: `${height} cm`, help: "Used for BMI and future body-size normalisation." },
    { label: "Weight", value: weight ? `${weight} kg` : "No data", help: "Manual or Garmin body composition." },
    { label: "BMI", value: bmi ? bmi.toFixed(1) : "No data", help: "Weight adjusted for height." },
    { label: "Body fat", value: m?.body_fat_pct ? `${m.body_fat_pct}%` : "No data", help: "Used in body-composition context." },
    { label: "Lean mass", value: m?.muscle_mass_kg ? `${m.muscle_mass_kg} kg` : "No data", help: "Manual or Garmin body composition." },
    { label: "VO2 Max", value: m?.vo2max ? `${m.vo2max} ml/kg/min` : "No data", help: "Main driver of Fitness Age." },
  ];
  return {
    name: titleCase(name),
    age: dashboard?.actual_age ? `${dashboard.actual_age.toFixed(1)}y` : "No age",
    metrics: profileMetrics,
    details,
  };
}

function exportProfileImage(dashboard: Dashboard | null, garminEmail: string | null) {
  const profile = profileSnapshot(dashboard, garminEmail);
  const width = 1200;
  const height = 720;
  const cells = profile.metrics.map((item, index) => {
    const x = 72 + (index % 3) * 352;
    const y = 286 + Math.floor(index / 3) * 156;
    return `
      <rect x="${x}" y="${y}" width="304" height="112" rx="24" fill="rgba(255,255,255,0.07)" stroke="rgba(255,255,255,0.12)" />
      <text x="${x + 24}" y="${y + 40}" fill="#8f98aa" font-size="22" font-family="Arial">${escapeXml(item.label)}</text>
      <text x="${x + 24}" y="${y + 82}" fill="#f4f7fb" font-size="34" font-weight="700" font-family="Arial">${escapeXml(item.value)}</text>
    `;
  }).join("");
  const svg = `
    <svg xmlns="http://www.w3.org/2000/svg" width="${width}" height="${height}" viewBox="0 0 ${width} ${height}">
      <defs>
        <linearGradient id="bg" x1="0" x2="1" y1="0" y2="1">
          <stop offset="0%" stop-color="#07100d" />
          <stop offset="55%" stop-color="#101216" />
          <stop offset="100%" stop-color="#141028" />
        </linearGradient>
        <radialGradient id="glow" cx="78%" cy="8%" r="80%">
          <stop offset="0%" stop-color="#6be3a4" stop-opacity="0.26"/>
          <stop offset="100%" stop-color="#6be3a4" stop-opacity="0"/>
        </radialGradient>
      </defs>
      <rect width="1200" height="720" fill="url(#bg)" />
      <rect width="1200" height="720" fill="url(#glow)" />
      <text x="72" y="90" fill="#6be3a4" font-size="24" letter-spacing="5" font-family="Arial">FORGE PROFILE</text>
      <text x="72" y="168" fill="#f4f7fb" font-size="72" font-weight="700" font-family="Arial">${escapeXml(profile.name)}</text>
      <text x="72" y="220" fill="#aeb7c7" font-size="28" font-family="Arial">Age ${escapeXml(profile.age)} · ${escapeXml(profile.details[3].value)} · ${escapeXml(profile.details[4].value)}</text>
      ${cells}
      <text x="72" y="650" fill="#6f7787" font-size="22" font-family="Arial">Generated by Forge · ${new Date().toISOString().slice(0, 10)}</text>
    </svg>
  `;
  const blob = new Blob([svg], { type: "image/svg+xml;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const img = new Image();
  img.onload = () => {
    const canvas = document.createElement("canvas");
    canvas.width = width;
    canvas.height = height;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;
    ctx.drawImage(img, 0, 0);
    URL.revokeObjectURL(url);
    const link = document.createElement("a");
    link.download = `forge-profile-${new Date().toISOString().slice(0, 10)}.png`;
    link.href = canvas.toDataURL("image/png");
    link.click();
  };
  img.src = url;
}

function biologyHeadline(stress: number | null | undefined, hrv: number | null | undefined, baseline: number | null | undefined) {
  if (stress !== null && stress !== undefined && stress >= 55) return "under stress load";
  if (hrv && baseline && hrv < baseline * 0.8) return "below baseline";
  if (stress !== null && stress !== undefined && stress < 30) return "stable";
  return "mixed";
}

function buildDisciplineCards(series: Record<string, MetricSeries | null>) {
  return [
    disciplineFromSeries("Aerobic base", "Cardio freshness", series.cardioLoad, "Cardio load freshness versus your own prior baseline."),
    disciplineFromSeries("Daily movement", "Movement freshness", series.steps, "Steps decay quickly, so this flags movement gaps early."),
    disciplineFromSeries("Intensity", "Hard-session freshness", series.vigorousMinutes, "Vigorous minutes fade faster than base aerobic work."),
    disciplineFromSeries("General activity", "Activity consistency", series.activeMinutes, "Active minutes reflect broad training consistency."),
  ];
}

function disciplineFromSeries(title: string, label: string, data: MetricSeries | null | undefined, detail: string) {
  const points = data?.series ?? [];
  const dated = points
    .filter((point) => point.value !== null && point.value !== undefined)
    .map((point) => ({ date: new Date(`${point.date}T00:00:00`), value: Number(point.value) }))
    .filter((point) => Number.isFinite(point.value));
  const recent = dated.slice(-7);
  const prior = dated.slice(0, -7);
  const recentSum = recent.reduce((sum, point) => sum + Math.max(0, point.value), 0);
  const priorDaily = prior.length
    ? prior.reduce((sum, point) => sum + Math.max(0, point.value), 0) / prior.length
    : dated.reduce((sum, point) => sum + Math.max(0, point.value), 0) / Math.max(dated.length, 1);
  const expected = Math.max(priorDaily * 7, 1);
  const ratio = recentSum / expected;
  const last = [...dated].reverse().find((point) => point.value > 0);
  const end = dated.length ? dated[dated.length - 1].date : new Date();
  const daysAgo = last ? Math.round((end.getTime() - last.date.getTime()) / 86_400_000) : null;
  const score = Math.round(Math.min(100, Math.max(0, ratio * 70)));
  const tone = ratio > 1.35 ? "warn" : ratio >= 0.65 ? "good" : "bad";
  const summary =
    daysAgo === null
      ? "No recent signal detected."
      : ratio > 1.35
        ? "Above your recent baseline. Space the next hard dose."
        : ratio >= 0.65
        ? `Maintained. Last meaningful signal was ${daysAgo === 0 ? "today" : `${daysAgo}d ago`}.`
        : `Due soon. Last meaningful signal was ${daysAgo === 0 ? "today" : `${daysAgo}d ago`}.`;
  const comparison = prior.length ? `7-day load is ${(ratio * 100).toFixed(0)}% of prior baseline.` : "Needs more history for a baseline.";
  return { title, label, detail: `${detail} ${comparison}`, score, tone, summary };
}

function scoreTone(value: number | null | undefined) {
  if (value === null || value === undefined) return null;
  return value >= 75 ? "good" : value >= 55 ? "warn" : "bad";
}

function hrvTone(value: number | null | undefined, baseline: number | null | undefined) {
  if (value === null || value === undefined) return null;
  if (!baseline) return value >= 55 ? "good" : value >= 35 ? "warn" : "bad";
  const ratio = value / baseline;
  return ratio >= 0.95 ? "good" : ratio >= 0.75 ? "warn" : "bad";
}

function rhrTone(value: number | null | undefined) {
  if (value === null || value === undefined) return null;
  return value <= 60 ? "good" : value <= 70 ? "warn" : "bad";
}

function stressTone(value: number | null | undefined) {
  if (value === null || value === undefined) return null;
  return value < 30 ? "good" : value < 55 ? "warn" : "bad";
}

function spo2Tone(value: number | null | undefined) {
  if (value === null || value === undefined) return null;
  return value >= 96 ? "good" : value >= 95 ? "warn" : "bad";
}

function respirationTone(value: number | null | undefined) {
  if (value === null || value === undefined) return null;
  return value >= 11 && value <= 17 ? "good" : value >= 9 && value <= 20 ? "warn" : "bad";
}

function sleepDebtTone(value: number | null | undefined) {
  if (value === null || value === undefined) return null;
  return value < 1 ? "good" : value < 2 ? "warn" : "bad";
}

function parseOptionalNumber(value: string) {
  const trimmed = value.trim();
  if (!trimmed) return null;
  const parsed = Number(trimmed);
  return Number.isFinite(parsed) ? parsed : null;
}

function syncFreshness(hours: number | null | undefined) {
  if (hours === null || hours === undefined) return "";
  if (hours < 0.2) return " · just synced";
  if (hours < 1) return " · synced under 1h ago";
  return ` · synced ${hours.toFixed(hours < 10 ? 1 : 0)}h ago`;
}

function labelForMetric(metric: string) {
  return metric.split("_").map((part) => part[0]?.toUpperCase() + part.slice(1)).join(" ");
}

function colorForMetric(metric: string) {
  if (metric.includes("sleep")) return "#8F7CFF";
  if (metric.includes("hrv") || metric.includes("recovery") || metric.includes("readiness")) return "#62E6D0";
  if (metric.includes("strain") || metric.includes("cardio")) return "#FF9B5F";
  if (metric.includes("stress") || metric.includes("rhr")) return "#F2C063";
  return "#6BE3A4";
}

function unitForMetric(metric: string) {
  if (metric === "hrv") return "ms";
  if (metric === "rhr" || metric === "max_hr" || metric === "hr_recovery") return "bpm";
  if (["sleep_hours", "deep_sleep", "rem_sleep", "light_sleep", "awake_time", "sleep_debt", "sleep_need"].includes(metric)) return "h";
  if (metric === "spo2" || metric === "body_battery" || metric === "body_fat") return "%";
  if (metric === "weight" || metric === "muscle_mass") return "kg";
  if (metric === "distance") return "km";
  if (metric.includes("minutes")) return "min";
  if (metric === "vo2max") return "ml/kg/min";
  return "";
}

function specialScore(metric: SpecialMetric | undefined) {
  return metric?.score ?? null;
}

function specialNumber(metric: SpecialMetric | undefined) {
  return typeof metric?.value === "number" ? metric.value : null;
}

function specialTone(metric: SpecialMetric | undefined): FocusMetric["tone"] | null {
  if (!metric) return null;
  if (metric.tone === "good" || metric.tone === "warn" || metric.tone === "bad" || metric.tone === "low") return metric.tone;
  if (metric.status === "good") return "good";
  if (metric.status === "watch") return "warn";
  if (metric.status === "alert") return "bad";
  return "neutral";
}

function specialSummary(metric: SpecialMetric | undefined, fallback: string) {
  return metric?.summary || fallback;
}

function showMetric(filter: MetricFilter, tone: FocusMetric["tone"] | null) {
  if (filter === "all") return true;
  if (filter === "missing") return tone === null || tone === "neutral";
  if (filter === "good") return tone === "good";
  if (filter === "watch") return tone === "warn" || tone === "low";
  if (filter === "poor") return tone === "bad";
  return true;
}

function formatFocusValue(value: number) {
  if (Math.abs(value) >= 1000) return Math.round(value).toLocaleString();
  if (Number.isInteger(value)) return String(value);
  return value.toFixed(Math.abs(value) < 10 ? 1 : 0);
}

function titleCase(value: string) {
  return value
    .split(/\s+/)
    .filter(Boolean)
    .map((part) => part[0]?.toUpperCase() + part.slice(1).toLowerCase())
    .join(" ");
}

function escapeXml(value: string) {
  return value
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&apos;");
}

function shiftDate(iso: string, days: number) {
  const d = new Date(`${iso}T00:00:00`);
  d.setDate(d.getDate() + days);
  return d.toISOString().slice(0, 10);
}
