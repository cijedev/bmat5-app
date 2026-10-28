"""
Phase 7 — Cultural intelligence (inclusive): affirmations, tone presets, context-aware copy for all users.

Tone presets adjust microcopy only; care-plan logic and safety prioritization stay in utils.py.
"""
from __future__ import annotations

from datetime import date

from .resources import RESOURCES

# Stored in UserPreference.data_json["tone_preset"]
TONE_PRESETS: tuple[str, ...] = (
    "warm_standard",
    "community_centered",
    "faith_informed",
    "direct_grounded",
)

TONE_LABELS: dict[str, str] = {
    "warm_standard": "Warm & clear (default)",
    "community_centered": "Community-centered",
    "faith_informed": "Faith-friendly (optional, inclusive)",
    "direct_grounded": "Direct & grounded",
}

# --- Daily affirmations (culturally grounded wellness; rotate deterministically) ---
AFFIRMATIONS: list[str] = [
    "Your pace is valid — rest is not a reward you have to earn.",
    "You belong in spaces that honor your whole story.",
    "Small steps still move you — consistency beats intensity.",
    "Asking for support is wisdom, not weakness.",
    "Your boundaries protect the energy you need to show up.",
    "You can hold hope and hard truth in the same breath.",
    "Healing is not linear; showing up today counts.",
    "You deserve care that sees you — not just your symptoms.",
    "Your body is carrying a lot; be gentle with the load.",
    "Connection is medicine — even one honest text can matter.",
    "You are allowed to prioritize peace over performance.",
    "Strength includes knowing when to pause.",
    "Your emotions are information, not inconvenience.",
    "You can name what hurts without rushing to fix it.",
    "Rest is a practice — not laziness.",
    "You are not behind; you are on your own path.",
    "Protecting your peace is a form of self-respect.",
    "You can celebrate progress that looks quiet to others.",
    "Your worth is not measured by productivity.",
    "You deserve softness on the hard days.",
    "Courage can sound like a whisper — still counts.",
    "You get to rewrite the story you tell yourself.",
    "Support looks different for everyone — yours is enough.",
    "You can hold joy without dismissing pain.",
    "Your voice matters — especially when it shakes.",
    "You are building resilience one check-in at a time.",
    "It is okay to outgrow what once kept you safe.",
    "You can choose one next right step — not the whole staircase.",
    "Your presence in this app is already an act of care.",
    "You are allowed to be both grateful and tired.",
]


def _stable_pick_index(user_id: int, day_key: str, n: int) -> int:
    h = 0
    for ch in f"{user_id}:{day_key}":
        h = (h * 31 + ord(ch)) & 0x7FFFFFFF
    return h % n if n else 0


def daily_affirmation(user_id: int, today: date | None = None) -> str:
    d = today or date.today()
    day_key = d.isoformat()
    idx = _stable_pick_index(user_id, day_key, len(AFFIRMATIONS))
    return AFFIRMATIONS[idx]


# --- Focus label tone maps (keys = exact strings from build_care_plan) ---
_FOCUS_KEYS = (
    "High stress",
    "Sleep support",
    "Low mood",
    "Depression symptoms",
    "Anxiety symptoms",
    "Maintain your momentum",
)

_FOCUS_TONE: dict[str, dict[str, str]] = {
    "warm_standard": {k: k for k in _FOCUS_KEYS},
    "community_centered": {
        "High stress": "A heavy load right now",
        "Sleep support": "Sleep needs extra care",
        "Low mood": "Mood needs gentle support",
        "Depression symptoms": "Depression symptoms deserve attention",
        "Anxiety symptoms": "Anxiety symptoms deserve attention",
        "Maintain your momentum": "Keep your rhythm going",
    },
    "faith_informed": {
        "High stress": "Stress is high — give yourself grace",
        "Sleep support": "Rest your body and mind tonight",
        "Low mood": "Low mood — be patient with your spirit",
        "Depression symptoms": "Depression symptoms — reach for support",
        "Anxiety symptoms": "Anxiety symptoms — slow breaths, small steps",
        "Maintain your momentum": "Steady faithfulness to small care",
    },
    "direct_grounded": {
        "High stress": "Stress is elevated",
        "Sleep support": "Prioritize sleep",
        "Low mood": "Low mood signal",
        "Depression symptoms": "PHQ signals elevated",
        "Anxiety symptoms": "GAD signals elevated",
        "Maintain your momentum": "Stay consistent",
    },
}


def _map_focus(f: str, tone: str) -> str:
    table = _FOCUS_TONE.get(tone) or _FOCUS_TONE["warm_standard"]
    return table.get(f, f)


# --- Recommended line maps (exact strings from build_care_plan) ---
_REC_LINE_KEYS = (
    "Tonight, prioritize a sleep wind-down over more screen time.",
    "Start with the 2-minute reset before trying anything longer.",
    "Connection may help today — try the Micro-connection action first.",
    "Grounding and short breathing exercises are likely your highest-yield tools today.",
    "You’re in a relatively steady zone — choose one quick action to maintain momentum.",
)

_REC_TONE: dict[str, dict[str, str]] = {
    "warm_standard": {k: k for k in _REC_LINE_KEYS},
    "community_centered": {
        "Tonight, prioritize a sleep wind-down over more screen time.": (
            "Tonight, let the people you trust see you resting — wind down before screens."
        ),
        "Start with the 2-minute reset before trying anything longer.": (
            "Try the 2-minute reset first — share later if it helps someone else too."
        ),
        "Connection may help today — try the Micro-connection action first.": (
            "Reach toward someone you trust — Micro-connection first."
        ),
        "Grounding and short breathing exercises are likely your highest-yield tools today.": (
            "Short grounding and breath work help the whole room you carry — start small."
        ),
        "You’re in a relatively steady zone — choose one quick action to maintain momentum.": (
            "You’re steady — one small action keeps the community-with-yourself going."
        ),
    },
    "faith_informed": {
        "Tonight, prioritize a sleep wind-down over more screen time.": (
            "Tonight, gift yourself rest as an act of care — ease into sleep before screens."
        ),
        "Start with the 2-minute reset before trying anything longer.": (
            "Begin with the 2-minute reset — a breath of grace before the rest."
        ),
        "Connection may help today — try the Micro-connection action first.": (
            "Connection can lighten the day — Micro-connection is a gentle step."
        ),
        "Grounding and short breathing exercises are likely your highest-yield tools today.": (
            "Grounding and short breaths can steady you — simple, sacred-small steps."
        ),
        "You’re in a relatively steady zone — choose one quick action to maintain momentum.": (
            "A steady season — one faithful small step maintains your care."
        ),
    },
    "direct_grounded": {
        "Tonight, prioritize a sleep wind-down over more screen time.": (
            "Tonight: sleep routine before more screen time."
        ),
        "Start with the 2-minute reset before trying anything longer.": (
            "Do the 2-minute reset first — then decide what’s next."
        ),
        "Connection may help today — try the Micro-connection action first.": (
            "Try Micro-connection first if you need people today."
        ),
        "Grounding and short breathing exercises are likely your highest-yield tools today.": (
            "Grounding + short breathing — highest yield today."
        ),
        "You’re in a relatively steady zone — choose one quick action to maintain momentum.": (
            "Steady zone — pick one action and keep going."
        ),
    },
}


def _map_rec(line: str, tone: str) -> str:
    table = _REC_TONE.get(tone) or _REC_TONE["warm_standard"]
    return table.get(line, line)


# --- Subtitles for "Today's focus" on dashboard ---
def today_focus_subtitle(tone: str, has_strong_signal: bool) -> str:
    if not has_strong_signal:
        if tone == "community_centered":
            return "One small move with your care plan keeps you connected to yourself."
        if tone == "faith_informed":
            return "Gentle consistency — not perfection — is enough today."
        if tone == "direct_grounded":
            return "Pick one low-effort reset and revisit tonight."
        return "Protect your baseline with one low-effort reset."

    if tone == "community_centered":
        return "Start with one small action below — you don’t have to carry it alone."
    if tone == "faith_informed":
        return "Start with one small step below — grace for whatever this day holds."
    if tone == "direct_grounded":
        return "Do one action below; check in again tonight."
    return "Start with one small action below and re-check tonight."


def _normalize_tone(prefs: dict) -> str:
    t = (prefs or {}).get("tone_preset") or "warm_standard"
    if t not in TONE_PRESETS:
        return "warm_standard"
    return t


def apply_cultural_layer(plan: dict, prefs: dict | None, user_id: int) -> dict:
    """
    Mutates plan in place: tone-mapped focus + recommended, adds plan['cultural'].
    """
    tone = _normalize_tone(prefs or {})
    orig_focus = list(plan.get("focus") or [])
    has_signal = len(orig_focus) > 1 or (
        len(orig_focus) == 1 and orig_focus[0] != "Maintain your momentum"
    )

    plan["focus"] = [_map_focus(f, tone) for f in orig_focus]
    plan["recommended"] = [_map_rec(r, tone) for r in plan.get("recommended") or []]

    subtitle = today_focus_subtitle(tone, has_signal)

    plan["cultural"] = {
        "tone": tone,
        "tone_label": TONE_LABELS.get(tone, TONE_LABELS["warm_standard"]),
        "affirmation": daily_affirmation(user_id),
        "today_focus_subtitle": subtitle,
    }

    hints = _action_hints(tone)
    for a in plan.get("actions") or []:
        key = a.get("key")
        if key and key in hints:
            a["cultural_hint"] = hints[key]

    return plan


def _action_hints(tone: str) -> dict[str, str]:
    """Short optional lines under tiny actions."""
    base = {
        "2-minute-reset": {
            "community_centered": "You’re allowed to reset in public or private — both count.",
            "faith_informed": "Four counts in, hold, out — a prayer can be that simple.",
            "direct_grounded": "Do five cycles. Stop if dizzy.",
        },
        "one-boundary-today": {
            "community_centered": "A boundary protects everyone’s peace — including yours.",
            "faith_informed": "A gentle no can be holy self-care.",
            "direct_grounded": "Pick one small no. Say it once.",
        },
        "micro-connection": {
            "community_centered": "One text can open the door to being seen.",
            "faith_informed": "Reach out — support can be part of your practice.",
            "direct_grounded": "One message. Keep it short.",
        },
        "sleep-downshift-10-min": {
            "community_centered": "Rest prepares you to show up for what matters tomorrow.",
            "faith_informed": "Let the day land — your body is listening.",
            "direct_grounded": "Lights down, phone away, ten minutes.",
        },
        "compassion-check-in": {
            "community_centered": "Self-compassion is how we stay in community with ourselves.",
            "faith_informed": "Speak to yourself with the patience you’d offer a friend.",
            "direct_grounded": "Finish the sentence. No editing.",
        },
    }
    out: dict[str, str] = {}
    for slug, tones in base.items():
        if tone in tones:
            out[slug] = tones[tone]
    return out


def representation_resources(highlight: bool) -> list[dict]:
    """Optional curated resources (tag=representation) for Culture page / care plan — available to anyone."""
    rep = [r for r in RESOURCES if r.get("tag") == "representation"]
    if not highlight:
        return []
    return list(rep)


def tone_streak_message(message: str, tone: str) -> str:
    if tone == "community_centered" and "milestone" in message.lower():
        return message + " Your steadiness matters."
    return message
