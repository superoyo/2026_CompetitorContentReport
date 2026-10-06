# -*- coding: utf-8 -*-
"""OpenRouter: one key, many models, for summarising a period.

The admin page lets whoever builds a multi-month deck pick which model writes
its summary. OpenRouter fronts them all behind one API and publishes each
model's price per token, which is what makes the estimate shown before a run
possible.

    OPENROUTER_API_KEY   required to run a summary (the model list is public);
                         OPENROUTER_API is accepted too
    OPENROUTER_MODELS    comma-separated ids to list first as recommended
"""
import json
import os
import threading
import time
import urllib.error
import urllib.request

API = "https://openrouter.ai/api/v1"
# OPENROUTER_API is the name already set on Railway; either works.
KEY = (os.environ.get("OPENROUTER_API_KEY") or os.environ.get("OPENROUTER_API") or "").strip()

RECOMMENDED = [m.strip() for m in os.environ.get("OPENROUTER_MODELS", ",".join([
    "anthropic/claude-sonnet-5.5",
    "anthropic/claude-opus-5.5",
    "openai/gpt-6.1-sol",
    "google/gemini-3.8-flash",
    "x-ai/grok-4.7",
    "qwen/qwen3.8-max-0902",
    "deepseek/deepseek-v4.1-flash",
])).split(",") if m.strip()]

# Thai runs to more tokens per character than English; 2.4 characters a token
# is on the cautious side for current tokenizers, so estimates err high.
CHARS_PER_TOKEN = 2.4
# Commentary written per page plus the group-wide parts, in output tokens.
OUT_PER_BRAND, OUT_FIXED = 1100, 900

_cache = {"at": 0, "models": []}
_lock = threading.Lock()


def configured():
    return bool(KEY)


def _float(v):
    try:
        f = float(v)
        return f if f >= 0 else None
    except (TypeError, ValueError):
        return None


def models():
    """Text models with a known price, recommended first; cached for an hour."""
    with _lock:
        if _cache["models"] and time.time() - _cache["at"] < 3600:
            return _cache["models"]
    req = urllib.request.Request(API + "/models", headers={"Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=30) as r:
        data = json.loads(r.read().decode()).get("data") or []
    out = []
    for m in data:
        mid = m.get("id") or ""
        arch = m.get("architecture") or {}
        if ":" in mid or "text" not in (arch.get("output_modalities") or ["text"]):
            continue                          # :batch / :free variants, image models
        p = m.get("pricing") or {}
        pin, pout = _float(p.get("prompt")), _float(p.get("completion"))
        if pin is None or pout is None:
            continue                          # routers with no fixed price
        params = m.get("supported_parameters") or []
        out.append({
            "id": mid,
            "name": m.get("name") or mid,
            "prompt": pin,
            "completion": pout,
            "max_out": (m.get("top_provider") or {}).get("max_completion_tokens"),
            "structured": "structured_outputs" in params or "response_format" in params,
            "recommended": mid in RECOMMENDED,
            "created": m.get("created") or 0,
        })
    rank = {mid: i for i, mid in enumerate(RECOMMENDED)}
    out.sort(key=lambda m: (rank.get(m["id"], len(rank)), m["id"]))
    with _lock:
        _cache.update(at=time.time(), models=out)
    return out


def find(model_id):
    try:
        return next((m for m in models() if m["id"] == model_id), None)
    except Exception:
        return None


def estimate(prompt_chars, n_brands, model_id):
    """{input_tokens, output_tokens, usd} — a rough figure, shown before a run."""
    m = find(model_id)
    tin = int(prompt_chars / CHARS_PER_TOKEN)
    tout = OUT_PER_BRAND * max(n_brands, 1) + OUT_FIXED
    usd = (tin * m["prompt"] + tout * m["completion"]) if m else None
    return {"input_tokens": tin, "output_tokens": tout,
            "usd": round(usd, 4) if usd is not None else None}


def estimate_calls(calls, model_id):
    """Several requests: calls = [(prompt characters, expected output tokens)]."""
    m = find(model_id)
    tin = sum(int(c / CHARS_PER_TOKEN) for c, _ in calls)
    tout = sum(o for _, o in calls)
    usd = (tin * m["prompt"] + tout * m["completion"]) if m else None
    return {"input_tokens": tin, "output_tokens": tout, "calls": len(calls),
            "usd": round(usd, 4) if usd is not None else None}


def chat(model_id, system, user, schema=None, max_tokens=32000, timeout=900):
    """One completion. Returns (text, usage dict, model actually used,
    finish_reason).

    Asks for schema-shaped JSON when the model supports it; if the request is
    refused for that reason, tries once more with the JSON asked for in words.
    usage carries OpenRouter's own `cost` in USD.
    """
    if not KEY:
        raise RuntimeError("ยังไม่ได้ตั้ง OPENROUTER_API_KEY บนเซิร์ฟเวอร์")
    m = find(model_id)
    if m and m.get("max_out"):
        max_tokens = min(max_tokens, int(m["max_out"]))
    body = {
        "model": model_id,
        "messages": [{"role": "system", "content": system},
                     {"role": "user", "content": user}],
        "max_tokens": max_tokens,
        "usage": {"include": True},
    }
    if schema and (m is None or m["structured"]):
        body["response_format"] = {"type": "json_schema", "json_schema": {
            "name": "report", "strict": True, "schema": schema}}
    try:
        got = _post(body, timeout)
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", "replace")[:400]
        if "response_format" in body and exc.code in (400, 404, 422):
            body.pop("response_format")
            got = _post(body, timeout)
        else:
            raise RuntimeError("OpenRouter ตอบ %d — %s" % (exc.code, detail))
    if got.get("error"):
        raise RuntimeError("OpenRouter: %s" % (got["error"].get("message") or got["error"]))
    choice = (got.get("choices") or [{}])[0]
    text = ((choice.get("message") or {}).get("content")) or ""
    return text, got.get("usage") or {}, got.get("model") or model_id, choice.get("finish_reason")


def _post(body, timeout):
    req = urllib.request.Request(
        API + "/chat/completions", data=json.dumps(body).encode(), method="POST",
        headers={"Authorization": "Bearer " + KEY, "Content-Type": "application/json",
                 "X-Title": "Competitor Content Report"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode())


def short_name(model_id):
    """What goes in a file name: 'anthropic/claude-sonnet-5.5' -> 'claude-sonnet-5.5'."""
    tail = (model_id or "").split("/")[-1]
    return "".join(c if c.isalnum() or c in ".-_" else "-" for c in tail) or "ai"
