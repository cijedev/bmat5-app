"""
Phase 8 — AI Wellness: OpenAI-powered reflection (optional; requires OPENAI_API_KEY).

Not clinical advice; responses are supportive and safety-bounded in the system prompt.
"""
from __future__ import annotations

from flask import current_app

_SYSTEM_PROMPT = """You are a warm, concise wellness companion inside Better Mental Wellness (BMW), a mental wellness app for all people seeking support.

Rules:
- You are NOT a therapist or doctor. Do not diagnose, label disorders, or prescribe treatment.
- If the user mentions self-harm, suicide, wanting to die, or being unsafe, respond with brief empathy and tell them to call or text 988 (US) or their local emergency number now — do not try to "fix" the crisis in chat.
- Encourage professional and community support when symptoms sound severe or persistent.
- Match the user's emotional tone: validate first, then offer 1–3 small, practical reflections or questions (not a wall of text).
- No markdown headings; plain paragraphs or short bullets with "-" only if helpful.
- Do not claim to know their medical history or results from BMW screenings unless the user pasted them.
- Avoid clichés and toxic positivity. Keep language respectful, culturally humble, and inclusive of all backgrounds — never assume race, gender, faith, or identity.
"""

_TONE_HINTS: dict[str, str] = {
    "warm_standard": "Use a warm, clear voice.",
    "community_centered": "Lean slightly toward connection, dignity, and collective care language where natural.",
    "faith_informed": "If spirituality might help, you may gently invite values or grace language — never assume a specific religion.",
    "direct_grounded": "Prefer short sentences and concrete suggestions.",
}


def ai_enabled() -> bool:
    try:
        key = current_app.config.get("OPENAI_API_KEY") or ""
    except RuntimeError:
        return False
    return bool(str(key).strip())


def generate_wellness_reflection(
    user_text: str,
    *,
    tone_preset: str,
    display_name: str,
) -> tuple[str | None, str | None]:
    """
    Call OpenAI Chat Completions. Returns (assistant_text, error_message_for_user).
    """
    if not ai_enabled():
        return None, "AI Wellness is not configured on this server (missing OPENAI_API_KEY)."

    text = (user_text or "").strip()
    if len(text) < 2:
        return None, "Please enter a bit more detail."

    tone_line = _TONE_HINTS.get(tone_preset, _TONE_HINTS["warm_standard"])
    user_block = f"The user's display name is {display_name}. Tone preference: {tone_line}\n\nUser message:\n{text}"
    return _chat_complete(user_block, temperature=0.65)


def generate_score_insight(
    *,
    display_name: str,
    tone_preset: str,
    mood: int | None,
    stress: int | None,
    sleep_hours: float | None,
    phq_score: int | None,
    phq_severity: str | None,
    phq_item9: int | None,
    gad_score: int | None,
    gad_severity: str | None,
) -> tuple[str | None, str | None]:
    """
    Explain latest check-in + PHQ/GAD values and recommend next steps.
    """
    if not ai_enabled():
        return None, "AI Wellness is not configured on this server (missing OPENAI_API_KEY)."

    tone_line = _TONE_HINTS.get(tone_preset, _TONE_HINTS["warm_standard"])

    metrics = [
        f"- mood (1-10): {mood if mood is not None else 'no recent check-in'}",
        f"- stress (1-10): {stress if stress is not None else 'no recent check-in'}",
        f"- sleep hours: {sleep_hours if sleep_hours is not None else 'no recent check-in'}",
        f"- PHQ-9 total: {phq_score if phq_score is not None else 'not completed'}",
        f"- PHQ-9 severity label: {phq_severity or 'n/a'}",
        f"- PHQ-9 item 9: {phq_item9 if phq_item9 is not None else 'n/a'}",
        f"- GAD-7 total: {gad_score if gad_score is not None else 'not completed'}",
        f"- GAD-7 severity label: {gad_severity or 'n/a'}",
    ]
    user_block = (
        f"The user's display name is {display_name}. Tone preference: {tone_line}\n\n"
        "Use these latest BMW values to explain what they likely mean in plain language.\n"
        "Important: this is educational support, not diagnosis.\n\n"
        "Output format:\n"
        "1) A short interpretation paragraph (2-4 sentences)\n"
        "2) 4-6 practical recommendations as '-' bullets\n"
        "3) A short 'When to seek extra support' paragraph.\n\n"
        "Metrics:\n"
        + "\n".join(metrics)
    )
    return _chat_complete(user_block, temperature=0.35)


def _chat_complete(user_block: str, *, temperature: float) -> tuple[str | None, str | None]:
    try:
        from openai import OpenAI
    except ImportError:
        return None, "OpenAI library is not installed. Run: pip install -r requirements.txt"

    model = (current_app.config.get("OPENAI_MODEL") or "llama-3.3-70b-versatile").strip()
    client_kwargs = {"api_key": current_app.config["OPENAI_API_KEY"].strip()}
    base_url = (current_app.config.get("OPENAI_BASE_URL") or "").strip()
    if base_url:
        client_kwargs["base_url"] = base_url
    client = OpenAI(**client_kwargs)
    if model.startswith("gpt-5") and hasattr(client, "responses"):
        return _responses_complete(client, model, user_block)

    base_messages = [
        {"role": "system", "content": _SYSTEM_PROMPT},
        {"role": "user", "content": user_block},
    ]
    attempts = _chat_attempts_for_model(model, base_messages, temperature)

    resp = None
    last_err = None
    for req in attempts:
        try:
            resp = client.chat.completions.create(**req)
            break
        except Exception as e:
            last_err = e
            current_app.logger.warning("OpenAI request attempt failed (%s): %s", ",".join(req.keys()), e)
            continue

    if resp is None:
        current_app.logger.warning("OpenAI request failed after all fallbacks: %s", last_err)
        return None, "AI Wellness could not respond right now. Please try again in a moment."

    choice = _extract_chat_text(resp)
    if not choice or not str(choice).strip():
        return None, "AI Wellness returned an empty response. Please try again."
    return str(choice).strip(), None


def _chat_attempts_for_model(model: str, base_messages: list[dict], temperature: float) -> list[dict]:
    """
    Build request attempts in an order that matches model quirks.
    GPT-5-class models tend to be stricter, so start with bare-minimum payloads.
    """
    if model.startswith("gpt-5"):
        return [
            {
                "model": model,
                "messages": base_messages,
            },
            {
                "model": model,
                "messages": base_messages,
                "max_completion_tokens": 700,
            },
            {
                "model": model,
                "messages": base_messages,
                "max_tokens": 700,
            },
            {
                "model": model,
                "messages": base_messages,
                "temperature": 1,
            },
        ]

    # Default ladder for 4o-style and similar chat-completions models.
    return [
        {
            "model": model,
            "messages": base_messages,
            "max_completion_tokens": 700,
            "temperature": temperature,
        },
        {
            "model": model,
            "messages": base_messages,
            "max_completion_tokens": 700,
        },
        {
            "model": model,
            "messages": base_messages,
            "max_tokens": 700,
        },
        {
            "model": model,
            "messages": base_messages,
        },
    ]


def _responses_complete(client, model: str, user_block: str) -> tuple[str | None, str | None]:
    """
    GPT-5-class models are more reliable with the Responses API.
    """
    try:
        resp = client.responses.create(
            model=model,
            instructions=_SYSTEM_PROMPT,
            input=user_block,
            max_output_tokens=700,
        )
    except Exception as e:
        current_app.logger.warning("OpenAI responses request failed: %s", e)
        return None, "AI Wellness could not respond right now. Please try again in a moment."

    text = getattr(resp, "output_text", None)
    if text and str(text).strip():
        return str(text).strip(), None

    # Fallback parse for SDK/model variants.
    try:
        parts = []
        for item in getattr(resp, "output", []) or []:
            for content in getattr(item, "content", []) or []:
                chunk = getattr(content, "text", None)
                if chunk:
                    parts.append(str(chunk))
        text = "\n".join(p for p in parts if p).strip()
        if text:
            return text, None
    except Exception:
        pass

    return None, "AI Wellness returned an empty response. Please try again."


def _extract_chat_text(resp) -> str | None:
    """
    Normalize text extraction across chat-completions variants.
    """
    if not getattr(resp, "choices", None):
        return None
    msg = resp.choices[0].message
    content = getattr(msg, "content", None)
    if isinstance(content, str):
        return content.strip()
    if isinstance(content, list):
        parts = []
        for item in content:
            if isinstance(item, dict):
                txt = item.get("text")
            else:
                txt = getattr(item, "text", None)
            if txt:
                parts.append(str(txt))
        joined = "\n".join(parts).strip()
        return joined or None
    return None
