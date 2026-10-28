from __future__ import annotations

from collections import defaultdict
from datetime import date, timedelta

from .resources import RESOURCES
from .cultural import apply_cultural_layer, representation_resources


def slugify_action(title: str) -> str:
    return (
        title.lower()
        .replace("’", "")
        .replace("'", "")
        .replace("(", "")
        .replace(")", "")
        .replace("/", "-")
        .replace(" ", "-")
    )


def action_tag_by_key() -> dict[str, str]:
    """Maps care-plan action keys to resource tags for learning + ranking."""
    return {
        slugify_action("2-minute reset"): "rest",
        slugify_action("One boundary today"): "boundaries",
        slugify_action("Micro-connection"): "support",
        slugify_action("Sleep downshift (10 min)"): "sleep",
        slugify_action("Compassion check-in"): "support",
    }


ACTION_TAG_BY_KEY = action_tag_by_key()

# Resource / care-plan topic tags (explicit prefs + learning)
FOCUS_TAGS = frozenset({"rest", "sleep", "support", "boundaries"})


def normalize_prefs_dict(raw: dict | None) -> dict:
    if raw is None:
        return {}
    tag_counts = raw.get("tag_counts")
    action_totals = raw.get("action_completion_totals")
    out = dict(raw)
    out["tag_counts"] = dict(tag_counts) if isinstance(tag_counts, dict) else {}
    out["action_completion_totals"] = dict(action_totals) if isinstance(action_totals, dict) else {}
    em = out.get("emphasize_tags") if isinstance(out.get("emphasize_tags"), list) else []
    st = out.get("steer_clear_tags") if isinstance(out.get("steer_clear_tags"), list) else []
    emphasize = [str(t) for t in em if t in FOCUS_TAGS]
    steer = [str(t) for t in st if t in FOCUS_TAGS and t not in emphasize]
    out["emphasize_tags"] = emphasize
    out["steer_clear_tags"] = steer
    # Phase 7 — cultural intelligence (stored in same JSON blob)
    tp = out.get("tone_preset")
    if tp is not None:
        tp = str(tp)
    valid_tones = frozenset({"warm_standard", "community_centered", "faith_informed", "direct_grounded"})
    out["tone_preset"] = tp if tp in valid_tones else "warm_standard"
    hr = out.get("highlight_representation")
    out["highlight_representation"] = True if hr is None else bool(hr)
    return out


def _stable_mix(*parts: str) -> int:
    h = 0
    for p in parts:
        for ch in p:
            h = (h * 31 + ord(ch)) & 0x7FFFFFFF
    return h


def _completion_counts_window(completions: list | None, num_days: int) -> dict[str, int]:
    if not completions or num_days < 1:
        return {}
    cutoff = date.today() - timedelta(days=num_days - 1)
    counts: dict[str, int] = defaultdict(int)
    for c in completions:
        if c.completed_date >= cutoff:
            counts[c.action_key] += 1
    return dict(counts)


def _steer_allowed_for_tag(
    tag: str | None,
    stress_high: bool,
    sleep_low: bool,
    mood_low: bool,
    phq_high: bool,
    gad_high: bool,
) -> bool:
    """Do not down-rank content that matches an active clinical signal."""
    if not tag:
        return True
    if tag == "sleep" and sleep_low:
        return False
    if tag == "rest" and (stress_high or gad_high):
        return False
    if tag == "support" and (phq_high or mood_low):
        return False
    if tag == "boundaries" and stress_high:
        return False
    return True


def apply_completion_learning(prefs: dict, action_key: str) -> None:
    """Mutates prefs with completion-derived signals (tag affinity, totals)."""
    prefs.setdefault("tag_counts", {})
    prefs.setdefault("action_completion_totals", {})
    prefs["action_completion_totals"][action_key] = prefs["action_completion_totals"].get(action_key, 0) + 1
    tag = ACTION_TAG_BY_KEY.get(action_key)
    if tag:
        prefs["tag_counts"][tag] = prefs["tag_counts"].get(tag, 0) + 1


def _checkin_trends(checkins: list | None) -> dict[str, float]:
    if not checkins or len(checkins) < 4:
        return {"mood_delta": 0.0, "stress_delta": 0.0}
    recent = checkins[:3]
    older = checkins[3:6]
    if not older:
        return {"mood_delta": 0.0, "stress_delta": 0.0}
    r_mood = sum(c.mood for c in recent) / len(recent)
    o_mood = sum(c.mood for c in older) / len(older)
    r_stress = sum(c.stress for c in recent) / len(recent)
    o_stress = sum(c.stress for c in older) / len(older)
    return {
        "mood_delta": r_mood - o_mood,
        "stress_delta": r_stress - o_stress,
    }


def _assessment_delta(assessments: list | None, kind: str) -> int:
    if not assessments:
        return 0
    same = [a for a in assessments if a.kind == kind]
    if len(same) < 2:
        return 0
    return same[0].total_score - same[1].total_score


def _last_completion_days_ago(completions: list | None, action_key: str) -> int | None:
    if not completions:
        return None
    best: date | None = None
    for c in completions:
        if c.action_key != action_key:
            continue
        if best is None or c.completed_date > best:
            best = c.completed_date
    if best is None:
        return None
    return (date.today() - best).days


def calculate_wellness_score(latest_phq, latest_gad, latest_checkin):
    """
    Returns a 0-100 score where higher is better.
    Weighted toward day-to-day signals but informed by PHQ/GAD.
    """
    score = 100.0

    if latest_checkin:
        mood_penalty = max(0, (10 - latest_checkin.mood)) * 3.0
        stress_penalty = max(0, latest_checkin.stress - 3) * 3.0
        if latest_checkin.sleep_hours < 6:
            sleep_penalty = (6 - latest_checkin.sleep_hours) * 4.0
        elif latest_checkin.sleep_hours > 9:
            sleep_penalty = (latest_checkin.sleep_hours - 9) * 2.0
        else:
            sleep_penalty = 0
        score -= mood_penalty + stress_penalty + sleep_penalty

    if latest_phq:
        score -= latest_phq.total_score * 1.2
    if latest_gad:
        score -= latest_gad.total_score * 1.0

    score = max(0, min(100, round(score)))

    if score >= 80:
        label = "Strong"
    elif score >= 65:
        label = "Steady"
    elif score >= 45:
        label = "Needs support"
    else:
        label = "High support"

    return score, label


def get_recent_insights(checkins, assessments):
    insights = []

    if checkins:
        low_sleep = [c for c in checkins if c.sleep_hours < 6]
        rested = [c for c in checkins if c.sleep_hours >= 6]

        if low_sleep and rested:
            avg_low_sleep_mood = sum(c.mood for c in low_sleep) / len(low_sleep)
            avg_rested_mood = sum(c.mood for c in rested) / len(rested)
            if avg_rested_mood - avg_low_sleep_mood >= 1:
                insights.append("Your mood tends to be lower after nights with less than 6 hours of sleep.")

        high_stress = [c for c in checkins if c.stress >= 7]
        if len(high_stress) >= 2:
            insights.append("You’ve had multiple high-stress check-ins recently — prioritize rest and small resets.")

        avg_mood = sum(c.mood for c in checkins[:7]) / min(len(checkins), 7)
        if avg_mood <= 4.5:
            insights.append("Your recent mood trend looks low — connection and gentle structure may help this week.")

        weekday_counts = defaultdict(list)
        for c in checkins:
            weekday_counts[c.created_at.strftime("%A")].append(c.stress)
        if weekday_counts:
            worst_day = max(weekday_counts.items(), key=lambda item: sum(item[1]) / len(item[1]))
            if len(worst_day[1]) >= 2 and sum(worst_day[1]) / len(worst_day[1]) >= 6.5:
                insights.append(f"Stress appears highest on {worst_day[0]}s in your recent check-ins.")

    if assessments:
        recent_phq = [a for a in assessments if a.kind == "PHQ9"][:3]
        recent_gad = [a for a in assessments if a.kind == "GAD7"][:3]
        if recent_phq and recent_phq[0].total_score >= 15:
            insights.append("Your recent PHQ-9 suggests a heavier mood burden — focus on low-effort support today.")
        if recent_gad and recent_gad[0].total_score >= 10:
            insights.append("Your recent GAD-7 suggests anxiety may be taking up more space right now.")

    # keep it concise
    return insights[:4]


def get_action_stats(completions):
    """Returns (completed_today_keys, streak_days, total_completed, last7_count)"""
    today = date.today()
    completed_today = {c.action_key for c in completions if c.completed_date == today}

    unique_dates = sorted({c.completed_date for c in completions}, reverse=True)
    streak = 0
    cursor = today
    date_set = set(unique_dates)
    while cursor in date_set:
        streak += 1
        cursor -= timedelta(days=1)

    last7 = sum(1 for c in completions if c.completed_date >= today - timedelta(days=6))
    return completed_today, streak, len(completions), last7


def build_care_plan(
    latest_phq,
    latest_gad,
    latest_checkin,
    checkins=None,
    assessments=None,
    completions=None,
    prefs=None,
    user_id: int | None = None,
):
    """
    Adaptive care plan with Phase 4 tuning:
    - Multi-factor scoring (symptoms + check-in trends + screening deltas)
    - Action rotation (7d / 14d / 28d windows + weekly tie-break)
    - Resource ranking: learned affinity + explicit emphasize / steer-clear
    """
    plan = {
        "focus": [],
        "actions": [],
        "resources": [],
        "recommended": [],
        "featured_resource": None,
    }

    prefs = normalize_prefs_dict(prefs)
    tag_learned = prefs.get("tag_counts", {})
    emphasize_tags = set(prefs.get("emphasize_tags", []))
    steer_clear_tags = set(prefs.get("steer_clear_tags", []))
    trends = _checkin_trends(checkins)
    phq_delta = _assessment_delta(assessments, "PHQ9")
    gad_delta = _assessment_delta(assessments, "GAD7")
    c7 = _completion_counts_window(completions, 7)
    c14 = _completion_counts_window(completions, 14)
    c28 = _completion_counts_window(completions, 28)
    y, week, _ = date.today().isocalendar()

    stress_high = bool(latest_checkin and latest_checkin.stress >= 7)
    sleep_low = bool(latest_checkin and latest_checkin.sleep_hours < 6)
    mood_low = bool(latest_checkin and latest_checkin.mood <= 4)
    phq_high = bool(latest_phq and latest_phq.total_score >= 10)
    gad_high = bool(latest_gad and latest_gad.total_score >= 10)

    if trends["mood_delta"] < -0.8:
        mood_low = True
    if trends["stress_delta"] > 0.8:
        stress_high = True
    if phq_delta >= 3:
        phq_high = True
    if gad_delta >= 3:
        gad_high = True

    burden = 0.0
    if stress_high:
        burden += 0.22
    if sleep_low:
        burden += 0.2
    if mood_low:
        burden += 0.18
    if phq_high:
        burden += 0.22
    if gad_high:
        burden += 0.18
    burden = min(1.0, burden)

    symptom_weight = 1.0 + 0.35 * burden
    trend_boost = 8.0 * max(0.0, trends["stress_delta"]) + 8.0 * max(0.0, -trends["mood_delta"])
    delta_boost = 6.0 * max(0, phq_delta) + 5.0 * max(0, gad_delta)

    # Focus signals
    if stress_high:
        plan["focus"].append("High stress")
    if sleep_low:
        plan["focus"].append("Sleep support")
    if mood_low:
        plan["focus"].append("Low mood")
    if phq_high:
        plan["focus"].append("Depression symptoms")
    if gad_high:
        plan["focus"].append("Anxiety symptoms")

    if not plan["focus"]:
        plan["focus"].append("Maintain your momentum")

    def score_action(base: float, stress_w=0.0, sleep_w=0.0, mood_w=0.0, phq_w=0.0, gad_w=0.0) -> float:
        p = base * symptom_weight
        p += stress_w * (18 if stress_high else 0)
        p += sleep_w * (20 if sleep_low else 0)
        p += mood_w * (16 if mood_low else 0)
        p += phq_w * (18 if phq_high else 0)
        p += gad_w * (16 if gad_high else 0)
        p += trend_boost + delta_boost
        return p

    # Adaptive actions
    plan["actions"].append({
        "key": slugify_action("2-minute reset"),
        "title": "2-minute reset",
        "how": "In 4… hold 2… out 6. Repeat 5 cycles.",
        "youtube": "ZufpZ1kODLc",
        "priority": score_action(72, stress_w=1.0, gad_w=1.0),
    })

    plan["actions"].append({
        "key": slugify_action("One boundary today"),
        "title": "One boundary today",
        "how": "Pick 1 small no: ‘I can’t take that on right now.’",
        "youtube": "Ws_HkA-kh6k",
        "priority": score_action(58, stress_w=1.0),
    })

    plan["actions"].append({
        "key": slugify_action("Micro-connection"),
        "title": "Micro-connection",
        "how": "Text one trusted person: ‘Can you check in with me tonight?’",
        "youtube": "AzVzv56me4s",
        "priority": score_action(62, mood_w=1.0, phq_w=1.0),
    })

    if sleep_low:
        plan["actions"].append({
            "key": slugify_action("Sleep downshift (10 min)"),
            "title": "Sleep downshift (10 min)",
            "how": "Dim lights → phone away → 5 breaths → write 3 worries → 1 next step tomorrow.",
            "youtube": "aEqlQvczMJQ",
            "priority": score_action(88, sleep_w=1.2),
        })

    if mood_low or phq_high:
        plan["actions"].append({
            "key": slugify_action("Compassion check-in"),
            "title": "Compassion check-in",
            "how": "Finish this sentence: ‘Today is hard, and I can still give myself ____.’",
            "youtube": "3VIL1L_ypMg",
            "priority": score_action(80, mood_w=0.8, phq_w=0.9),
        })

    # Explicit topic prefs (actions)
    for a in plan["actions"]:
        tag = ACTION_TAG_BY_KEY.get(a["key"])
        if tag in emphasize_tags:
            a["priority"] += 15
        if tag in steer_clear_tags and _steer_allowed_for_tag(
            tag, stress_high, sleep_low, mood_low, phq_high, gad_high
        ):
            a["priority"] -= 22

    # Rotation: 7d / 14d / 28d windows + stable weekly variety for ties
    uid = str(user_id or 0)
    for a in plan["actions"]:
        k = a["key"]
        n7, n14, n28 = c7.get(k, 0), c14.get(k, 0), c28.get(k, 0)
        rotation_penalty = (
            min(34, n7 * 13)
            + min(30, max(0, n14 - n7) * 8)
            + min(16, max(0, n28 - n14) * 3)
        )
        a["priority"] -= rotation_penalty
        last_days = _last_completion_days_ago(completions, k)
        a["_last_done"] = last_days if last_days is not None else 9999
        a["_tie"] = _stable_mix(uid, str(week), str(y), k)

    plan["actions"] = sorted(
        plan["actions"],
        key=lambda x: (-x["priority"], x["_last_done"], x["_tie"]),
    )
    for a in plan["actions"]:
        a.pop("_last_done", None)
        a.pop("_tie", None)

    # Resource tags + adaptive ranking + learned affinity
    tags = {"boundaries"}
    if stress_high:
        tags.add("rest")
    if sleep_low:
        tags.add("sleep")
    if phq_high:
        tags.add("support")
    if gad_high:
        tags.add("rest")
        tags.add("support")

    resources = [r for r in RESOURCES if r.get("tag") in tags]

    def resource_priority(r):
        tag = r.get("tag")
        score = 0.0
        if tag == "sleep" and sleep_low:
            score += 100
        if tag == "rest" and (stress_high or gad_high):
            score += 95
        if tag == "support" and (phq_high or mood_low):
            score += 90
        if tag == "boundaries" and stress_high:
            score += 85
        learned = float(tag_learned.get(tag, 0))
        score += min(28.0, learned * 3.5)
        if tag in emphasize_tags:
            score += 18
        if tag in steer_clear_tags and _steer_allowed_for_tag(
            tag, stress_high, sleep_low, mood_low, phq_high, gad_high
        ):
            score -= 30
        return max(0.0, score)

    resources = sorted(resources, key=resource_priority, reverse=True)
    plan["resources"] = resources
    plan["featured_resource"] = resources[0] if resources else None

    # Recommended for you section
    recommended = []
    if sleep_low:
        recommended.append("Tonight, prioritize a sleep wind-down over more screen time.")
    if stress_high:
        recommended.append("Start with the 2-minute reset before trying anything longer.")
    if mood_low or phq_high:
        recommended.append("Connection may help today — try the Micro-connection action first.")
    if gad_high:
        recommended.append("Grounding and short breathing exercises are likely your highest-yield tools today.")

    if not recommended:
        recommended.append("You’re in a relatively steady zone — choose one quick action to maintain momentum.")

    plan["recommended"] = recommended[:3]

    apply_cultural_layer(plan, prefs, user_id or 0)
    plan["representation_spotlight"] = representation_resources(bool((prefs or {}).get("highlight_representation", True)))
    return plan


def mask_email(email: str) -> str:
    try:
        local, domain = email.split("@", 1)
        if len(local) <= 2:
            local_mask = local[0] + "*"
        else:
            local_mask = local[0] + "*" * (len(local) - 2) + local[-1]
        return f"{local_mask}@{domain}"
    except Exception:
        return "***"


def safe_redirect_target(next_url: str | None, fallback: str) -> str:
    """Only allow relative same-app paths (open-redirect safe).

    Accepts paths that start with a single `/` (e.g. `/careplan`).
    Rejects scheme-relative (`//…`), absolute URLs (`http:`, `https:`),
    backslashes, and empty/whitespace values.
    """
    if not next_url:
        return fallback
    candidate = str(next_url).strip()
    if not candidate:
        return fallback
    if "\\" in candidate or "\x00" in candidate:
        return fallback
    lower = candidate.lower()
    if lower.startswith(("http:", "https:", "javascript:", "data:")):
        return fallback
    if not candidate.startswith("/"):
        return fallback
    if candidate.startswith("//"):
        return fallback
    return candidate

