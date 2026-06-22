"""Coach service — real metrics + AI narration."""
from __future__ import annotations
import json
from datetime import date, timedelta
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.core.config import get_settings
from app.core.date_utils import day_progress, get_active_date
from app.models.health import CoachSummary, HealthSnapshot
from app.services import goals as goals_svc
from app.services.insights import dashboard_insights
from app.services.profile import actual_age_years
from app.services.scoring import fitness_age_drivers, biological_age_drivers, compute_fitness_age, compute_biological_age


def _latest_snap(db: Session, user_id: int) -> HealthSnapshot | None:
    d = get_active_date()
    row = db.execute(
        select(HealthSnapshot).where(HealthSnapshot.user_id == user_id, HealthSnapshot.date == d)
    ).scalar_one_or_none()
    if not row:
        # fall back to most recent
        row = db.execute(
            select(HealthSnapshot).where(
                HealthSnapshot.user_id == user_id,
                HealthSnapshot.source == "garmin",
            )
            .order_by(HealthSnapshot.date.desc()).limit(1)
        ).scalar_one_or_none()
    return row


def _7d_snaps(db: Session, user_id: int) -> list[HealthSnapshot]:
    end = get_active_date()
    start = end - timedelta(days=6)
    return list(db.execute(
        select(HealthSnapshot)
        .where(HealthSnapshot.user_id == user_id, HealthSnapshot.date >= start)
        .order_by(HealthSnapshot.date.asc())
    ).scalars().all())


def build_context(db: Session, user_id: int) -> dict:
    s = get_settings()
    actual_age = actual_age_years(db, user_id)
    snap = _latest_snap(db, user_id)
    snaps_7d = _7d_snaps(db, user_id)
    goals = goals_svc.list_today(db, user_id)
    stats = goals_svc.daily_completion_stats(db, user_id, get_active_date())
    progress = day_progress(wake_hour=s.wake_hour, sleep_hour=s.sleep_hour)

    def v(field, default=None):
        return getattr(snap, field, None) if snap else default

    def avg7(field):
        vals = [getattr(sn, field) for sn in snaps_7d if getattr(sn, field) is not None]
        return round(sum(vals) / len(vals), 1) if vals else None

    def latest_v(field):
        row = db.execute(
            select(HealthSnapshot)
            .where(HealthSnapshot.user_id == user_id, getattr(HealthSnapshot, field).isnot(None))
            .order_by(HealthSnapshot.date.desc())
            .limit(1)
        ).scalar_one_or_none()
        return getattr(row, field, None) if row else None

    if snap:
        for sparse_field in ("vo2max", "hr_recovery", "weight_kg", "body_fat_pct", "muscle_mass_kg", "bmi"):
            if getattr(snap, sparse_field, None) is None:
                setattr(snap, sparse_field, latest_v(sparse_field))

    fit_age, fit_status = compute_fitness_age(snap, actual_age) if snap else (None, None)
    bio_age, bio_status = compute_biological_age(snap, actual_age) if snap else (None, None)
    fit_drivers = fitness_age_drivers(snap, actual_age) if snap else []
    bio_drivers = biological_age_drivers(snap, actual_age) if snap else []
    history = dashboard_insights(db, user_id, "90d", get_active_date())

    return {
        "actual_age": actual_age,
        "date": get_active_date().isoformat(),
        "has_data": snap is not None,
        "day_phase": progress["phase"],
        "day_percent": progress["percent"],
        # Today
        "recovery": v("recovery"),
        "strain": v("strain"),
        "target_strain": v("target_strain"),
        "sleep_score": v("sleep_score"),
        "sleep_hours": round(v("sleep_minutes") / 60, 1) if v("sleep_minutes") else None,
        "sleep_debt_hours": round(v("sleep_debt_minutes") / 60, 1) if v("sleep_debt_minutes") else None,
        "hrv": v("hrv_ms"),
        "hrv_baseline": v("hrv_baseline_ms"),
        "rhr": v("rhr_bpm"),
        "rhr_baseline": v("rhr_baseline_bpm"),
        "body_battery": v("body_battery"),
        "stress": v("stress"),
        "spo2": v("spo2_avg"),
        "cardio_load": v("cardio_load"),
        "load_balance": v("load_balance"),
        "vo2max": v("vo2max"),
        # 7d averages
        "avg_7d_hrv": avg7("hrv_ms"),
        "avg_7d_rhr": avg7("rhr_bpm"),
        "avg_7d_sleep": round(avg7("sleep_minutes") / 60, 1) if avg7("sleep_minutes") else None,
        "avg_7d_stress": avg7("stress"),
        # Age
        "fitness_age": fit_age,
        "fitness_age_status": fit_status,
        "fitness_age_delta": round(fit_age - actual_age, 1) if fit_age else None,
        "biological_age": bio_age,
        "biological_age_status": bio_status,
        "biological_age_delta": round(bio_age - actual_age, 1) if bio_age else None,
        "fitness_age_drivers": fit_drivers or [],
        "biological_age_drivers": bio_drivers or [],
        "history_flags": history.get("flags", []),
        "history_insights": history.get("insights", []),
        "history_patterns": history.get("patterns", []),
        # Goals
        "goals_total": stats["total"],
        "goals_completed": stats["completed"],
        "goals_pending": stats["total"] - stats["completed"],
    }


def recommendations(db: Session, user_id: int) -> dict:
    """Deterministic recommendations — always works without AI."""
    ctx = build_context(db, user_id)
    lines = []

    if not ctx["has_data"]:
        return {
            "headline": "Connect Garmin to get your first brief",
            "summary": "No health data yet. Sync Garmin to see personalised coaching.",
            "observations": [],
            "actions": [{"text": "Sync Garmin data to get started", "priority": "high"}],
            "risks": [],
            "confidence": 0.0,
            "context": ctx,
        }

    # Training
    rec = ctx.get("recovery")
    strain = ctx.get("strain")
    target = ctx.get("target_strain")
    if rec is not None:
        if rec >= 70:
            lines.append({"kind": "training", "title": "Push", "body": f"Recovery {rec}. Your body is primed — aim for strain near {target or 'target'}.", "tone": "good"})
        elif rec >= 50:
            lines.append({"kind": "training", "title": "Moderate", "body": f"Recovery {rec}. Keep strain controlled and prioritise quality over volume.", "tone": "warn"})
        else:
            lines.append({"kind": "training", "title": "Recover", "body": f"Recovery {rec}. Avoid intensity. Easy movement or full rest only.", "tone": "bad"})

    # Sleep debt
    debt = ctx.get("sleep_debt_hours")
    if debt and debt > 1.5:
        lines.append({"kind": "sleep", "title": "Sleep debt accumulating", "body": f"{debt}h sleep debt. Move bedtime forward 30 minutes and protect sleep above all else tonight.", "tone": "warn"})

    # HRV vs baseline
    hrv = ctx.get("hrv")
    hrv_base = ctx.get("hrv_baseline")
    if hrv and hrv_base and hrv < hrv_base * 0.85:
        lines.append({"kind": "hrv", "title": "HRV suppressed", "body": f"HRV {hrv}ms is {round((1 - hrv/hrv_base)*100)}% below your {hrv_base}ms baseline. Likely sign of incomplete recovery or elevated stress.", "tone": "warn"})

    # RHR elevated
    rhr = ctx.get("rhr")
    rhr_base = ctx.get("rhr_baseline")
    if rhr and rhr_base and rhr > rhr_base + 5:
        lines.append({"kind": "rhr", "title": "RHR elevated", "body": f"Resting HR is {rhr - rhr_base:.0f}bpm above your {rhr_base}bpm baseline. Keep intensity controlled today.", "tone": "warn"})

    # Fitness Age
    fit_delta = ctx.get("fitness_age_delta")
    if fit_delta is not None:
        if fit_delta <= -3:
            lines.append({"kind": "fitness_age", "title": f"Fitness Age {abs(fit_delta)}y younger", "body": "Your cardiovascular fitness is tracking well ahead of your actual age.", "tone": "good"})
        elif fit_delta >= 3:
            top_driver = next((d for d in ctx["fitness_age_drivers"] if d["direction"] == "hurting"), None)
            tip = f" Focus on {top_driver['name']} first." if top_driver else ""
            lines.append({"kind": "fitness_age", "title": f"Fitness Age {fit_delta}y older", "body": f"Cardiovascular fitness is behind your actual age.{tip}", "tone": "warn"})

    # Bio Age
    bio_delta = ctx.get("biological_age_delta")
    if bio_delta is not None and bio_delta >= 2:
        top_bio = next((d for d in ctx["biological_age_drivers"] if d["direction"] == "hurting"), None)
        tip = f" {top_bio['name']} is the main limiter." if top_bio else ""
        lines.append({"kind": "biological_age", "title": f"Biological Age {bio_delta}y older", "body": f"Your physiological markers are ageing faster than your years.{tip}", "tone": "warn"})

    # Goals
    if ctx["goals_total"] == 0:
        lines.append({"kind": "goals", "title": "Set the day's intent", "body": "No goals on the board. Add 3 things you'll be glad you did today.", "tone": "neutral"})
    elif ctx["goals_total"] > 6:
        lines.append({"kind": "goals", "title": "Overloaded list", "body": f"{ctx['goals_total']} goals is too many. Cut to 3 high-leverage items.", "tone": "warn"})

    for flag in ctx.get("history_flags", [])[:2]:
        lines.append({
            "kind": flag.get("metric", "history"),
            "title": flag.get("title", "Metric flag"),
            "body": flag.get("detail", ""),
            "tone": "bad" if flag.get("severity") == "alert" else "warn",
        })

    for pattern in ctx.get("history_patterns", [])[:2]:
        if pattern.get("confidence") != "low":
            lines.append({
                "kind": pattern.get("metric", "pattern"),
                "title": pattern.get("title", "Pattern detected"),
                "body": pattern.get("summary", ""),
                "tone": "neutral",
            })

    headline = lines[0]["body"] if lines else "All metrics steady."
    summary = " ".join(l["body"] for l in lines[:3])

    return {
        "headline": headline,
        "summary": summary,
        "observations": [{"text": l["body"], "tone": l["tone"], "kind": l["kind"]} for l in lines],
        "actions": _build_actions(ctx),
        "risks": _build_risks(ctx),
        "confidence": 0.85 if ctx["has_data"] else 0.0,
        "context": ctx,
    }


def _build_actions(ctx: dict) -> list[dict]:
    actions = []
    if ctx.get("sleep_debt_hours", 0) and ctx["sleep_debt_hours"] > 1:
        actions.append({"text": "Move bedtime forward 30 minutes tonight", "priority": "high"})
    recovery = ctx.get("recovery")
    if recovery is not None and recovery < 50:
        actions.append({"text": "No high-intensity training today — walk or rest", "priority": "high"})
    if ctx.get("stress", 0) and ctx["stress"] > 50:
        actions.append({"text": "10-minute breathing session before the next work block", "priority": "medium"})
    bedtime = next((p for p in ctx.get("history_patterns", []) if p.get("id") == "best_bedtime" and p.get("confidence") != "low"), None)
    if bedtime:
        actions.append({"text": bedtime["title"].replace("Best sleep scores cluster around", "Start wind-down before"), "priority": "medium"})
    if ctx.get("goals_pending", 0) > 0 and ctx.get("day_phase") in ("EVENING", "BEDTIME"):
        actions.append({"text": "Push unfinished low-priority goals to tomorrow", "priority": "medium"})
    return actions


def _build_risks(ctx: dict) -> list[dict]:
    risks = []
    if ctx.get("sleep_debt_hours", 0) and ctx["sleep_debt_hours"] > 2:
        risks.append({"text": "Sleep debt above 2h is affecting recovery and cognitive performance", "severity": "high"})
    if ctx.get("rhr") and ctx.get("rhr_baseline") and ctx["rhr"] > ctx["rhr_baseline"] + 8:
        risks.append({"text": "RHR significantly elevated — possible illness, overtraining, or poor recovery", "severity": "high"})
    if ctx.get("spo2") and ctx["spo2"] < 93:
        risks.append({"text": f"SpO2 at {ctx['spo2']}% — below normal range. Monitor closely.", "severity": "high"})
    return risks


def generate_ai_brief(db: Session, user_id: int) -> dict:
    """Generate AI-narrated brief and store to DB."""
    ctx = build_context(db, user_id)
    det_result = recommendations(db, user_id)
    s = get_settings()

    if not s.openai_api_key:
        # Save deterministic result
        _save_summary(db, user_id, det_result, used_ai=False)
        return {**det_result, "used_ai": False, "warning": "OPENAI_API_KEY not set — deterministic fallback used"}

    prompt = f"""You are the Forge health coach. Based on this data, write a concise, premium coach brief.

Context:
{json.dumps({k: v for k, v in ctx.items() if k != 'fitness_age_drivers' and k != 'biological_age_drivers'}, indent=2)}

Existing observations:
{json.dumps(det_result['observations'], indent=2)}

Deterministic history flags, trends, and patterns:
{json.dumps({
    "flags": ctx.get("history_flags", []),
    "insights": ctx.get("history_insights", []),
    "patterns": ctx.get("history_patterns", []),
}, indent=2)}

Rules:
- Bevel/Whoop tone: calm, specific, no fluff
- Never say "listen to your body" or generic advice
- Never invent numbers not in the context
- Prefer pattern-backed statements and mention the evidence count or correlation when present
- Max 3 sentences for headline summary
- Return JSON only:
{{
  "headline": "...",
  "summary": "...",
  "observations": [{{"text": "...", "tone": "good|warn|bad|neutral", "kind": "..."}}],
  "actions": [{{"text": "...", "priority": "high|medium|low"}}],
  "risks": [{{"text": "...", "severity": "high|medium|low"}}]
}}"""

    try:
        from openai import OpenAI
        client = OpenAI(api_key=s.openai_api_key)
        resp = client.chat.completions.create(
            model=s.openai_model,
            messages=[{"role": "user", "content": prompt}],
            response_format={"type": "json_object"},
            max_tokens=800,
            temperature=0.3,
        )
        data = json.loads(resp.choices[0].message.content or "{}")
        result = {**det_result, **data, "confidence": 0.92, "used_ai": True}
        _save_summary(db, user_id, result, used_ai=True)
        return result
    except Exception as e:
        det_result["warning"] = f"AI generation failed: {e}"
        _save_summary(db, user_id, det_result, used_ai=False)
        return det_result


def _save_summary(db: Session, user_id: int, result: dict, used_ai: bool):
    d = get_active_date()
    existing = db.execute(
        select(CoachSummary)
        .where(CoachSummary.user_id == user_id, CoachSummary.date == d)
        .order_by(CoachSummary.id.desc())
        .limit(1)
    ).scalar_one_or_none()
    if existing:
        existing.headline = result.get("headline", "")
        existing.summary = result.get("summary", "")
        existing.observations_json = json.dumps(result.get("observations", []))
        existing.actions_json = json.dumps(result.get("actions", []))
        existing.risks_json = json.dumps(result.get("risks", []))
        existing.confidence = result.get("confidence", 0.7)
        existing.used_ai = used_ai
    else:
        db.add(CoachSummary(
            user_id=user_id,
            date=d,
            headline=result.get("headline", ""),
            summary=result.get("summary", ""),
            observations_json=json.dumps(result.get("observations", [])),
            actions_json=json.dumps(result.get("actions", [])),
            risks_json=json.dumps(result.get("risks", [])),
            confidence=result.get("confidence", 0.7),
            used_ai=used_ai,
        ))
    db.commit()
