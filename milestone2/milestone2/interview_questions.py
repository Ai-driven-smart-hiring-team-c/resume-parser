"""
interview_questions.py
Role-specific interview question generation with three engines, tried in order:

  1. An OpenAI-compatible LLM server  (LM Studio, Ollama, or any hosted API)
       - auto-detected on localhost:1234 (LM Studio) and localhost:11434 (Ollama)
       - or set LLM_BASE_URL (+ LLM_API_KEY, LLM_MODEL) for a hosted API
       - by far the fastest option: quantised models run in an optimised engine
  2. A local HuggingFace model (Qwen2.5, via transformers)   -- slow on CPU
       - model name from QUESTION_MODEL, switch off with USE_LOCAL_MODEL=0
       - warm_up() loads it in the background so the first click is not slow
  3. A ready-made question bank  -- instant, no AI

generate_questions_with_info() returns (questions, source) so the UI can say
which engine actually produced the questions.
"""

import json
import os
import random
import re
import threading
import time
import urllib.error
import urllib.request

AUTO_PROBE_URLS = ["http://localhost:1234/v1", "http://localhost:11434/v1"]   # LM Studio, Ollama
SOURCE_SERVER = "llm_server"
SOURCE_LOCAL = "local_model"
SOURCE_BANK = "question_bank"


def _cfg():
    """Read settings at call time so env vars / Streamlit secrets set later still count."""
    return {
        "base_url": os.environ.get("LLM_BASE_URL", "").strip().rstrip("/"),
        "api_key": os.environ.get("LLM_API_KEY", "lm-studio").strip() or "lm-studio",
        "model": os.environ.get("LLM_MODEL", "").strip(),
        "use_local": os.environ.get("USE_LOCAL_MODEL", "1").strip() != "0",
        "local_model": os.environ.get("QUESTION_MODEL", "Qwen/Qwen2.5-1.5B-Instruct").strip(),
    }


# ============================================================
# Ready-made bank (last resort, also used to top up short answers)
# ============================================================

QUESTION_BANK = {
    "Technical": [
        "Describe a project where you applied {role} skills to solve a real problem.",
        "Which tools or frameworks do you rely on most as a {role}, and why?",
        "Walk me through how you would debug a production issue in a {role} context.",
        "How do you decide between two technical approaches when working as a {role}?",
        "What does a good code or design review look like for a {role}?",
        "Explain a technical concept from your {role} work to someone who is not technical.",
    ],
    "Behavioral": [
        "Tell me about a time you disagreed with a teammate on a {role}-related decision.",
        "Describe a situation where you had to learn a new skill quickly for a {role} task.",
        "Tell me about a deadline you were at risk of missing and what you did.",
        "Describe a mistake you made on a project and what you changed afterwards.",
        "Give an example of feedback that changed how you work.",
    ],
    "Aptitude": [
        "How do you prioritise tasks when several {role} responsibilities compete for your time?",
        "Describe your approach to estimating how long a new {role} task will take.",
        "If a system you own slows down suddenly, how do you narrow down the cause?",
        "You have three urgent requests and time for one. How do you choose?",
        "How would you check that your own work is correct before handing it over?",
    ],
}


def _from_bank(role, question_type, n, exclude=()):
    pool = [q.format(role=role) for q in QUESTION_BANK.get(question_type, QUESTION_BANK["Technical"])]
    taken = {e.lower() for e in exclude}
    pool = [q for q in pool if q.lower() not in taken]
    random.shuffle(pool)
    out = pool[:n]
    while len(out) < n:                                    # bank exhausted: generic filler
        out.append(f"Describe your experience that is most relevant to the {role} role.")
    return out


# ============================================================
# Prompt + parsing (shared by both AI engines)
# ============================================================

TYPE_HINTS = {
    "Technical": "Test concrete technical knowledge and hands-on skills a {role} uses.",
    "Behavioral": "Ask about real past situations: teamwork, conflict, pressure, learning from mistakes.",
    "Aptitude": "Test logical reasoning, problem solving and prioritisation with short scenarios.",
}


def _messages(role, question_type, difficulty, n, avoid):
    system = (
        "You are an expert interviewer. Reply ONLY with a numbered list, one question per line. "
        "Every question is a single sentence of at most 25 words. No introduction and no answers."
    )
    user = (
        f"Write {n} different {difficulty.lower()}-difficulty {question_type.lower()} interview "
        f"questions for a {role} candidate. "
        + TYPE_HINTS.get(question_type, "").format(role=role)
    )
    if avoid:
        user += " Do not repeat these: " + " | ".join(avoid[:6])
    return [{"role": "system", "content": system}, {"role": "user", "content": user}]


def _parse_questions(raw_text):
    text = re.sub(r"<think>.*?</think>", "", raw_text or "", flags=re.DOTALL | re.IGNORECASE)
    questions, seen = [], set()
    for line in re.split(r"\n|(?=\b\d+[\.\)]\s)", text):
        line = re.sub(r"^\s*(?:\d+[\.\)]|[-*\u2022])\s*", "", line.strip())
        line = line.replace("**", "").strip()
        if len(line) < 16 or line.endswith(":"):          # junk fragments and "Here are 3 questions:"
            continue
        if line.lower() in seen:
            continue
        seen.add(line.lower())
        questions.append(line)
    return questions


# ============================================================
# Engine 1: OpenAI-compatible server (LM Studio / Ollama / hosted API)
# ============================================================

_server_cache = {"checked_at": 0.0, "server": None}
_LOCAL_OPENER = urllib.request.build_opener(urllib.request.ProxyHandler({}))   # never send localhost via a proxy


def _http_json(method, url, api_key, payload=None, timeout=10):
    data = json.dumps(payload).encode("utf-8") if payload is not None else None
    req = urllib.request.Request(
        url, data=data, method=method,
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {api_key}"},
    )
    is_local = "://localhost" in url or "://127.0.0.1" in url
    opener = _LOCAL_OPENER.open if is_local else urllib.request.urlopen
    with opener(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _pick_model(models_payload, preferred=""):
    ids = [m.get("id", "") for m in (models_payload or {}).get("data", []) if isinstance(m, dict)]
    ids = [i for i in ids if i and "embed" not in i.lower()]          # embedding models cannot chat
    if preferred and preferred in ids:
        return preferred
    return ids[0] if ids else ""


def _find_server(force=False):
    """Returns (base_url, model, api_key) for a reachable chat server, or None.
    The answer is cached briefly so page reruns do not keep probing."""
    cfg = _cfg()
    now = time.time()
    ttl = 30 if _server_cache["server"] else 10
    if not force and now - _server_cache["checked_at"] < ttl:
        return _server_cache["server"]

    found = None
    if cfg["base_url"]:
        if cfg["model"]:
            found = (cfg["base_url"], cfg["model"], cfg["api_key"])     # trust explicit config
        else:
            try:
                model = _pick_model(_http_json("GET", f"{cfg['base_url']}/models", cfg["api_key"], timeout=5), "")
                found = (cfg["base_url"], model, cfg["api_key"]) if model else None
            except (OSError, ValueError):
                found = None
    else:
        for base in AUTO_PROBE_URLS:
            try:
                model = _pick_model(_http_json("GET", f"{base}/models", cfg["api_key"], timeout=0.8), cfg["model"])
            except (OSError, ValueError):
                continue
            if model:
                found = (base, model, cfg["api_key"])
                break

    _server_cache.update(checked_at=now, server=found)
    return found


def _generate_via_server(server, messages, n):
    base, model, api_key = server
    payload = {
        "model": model, "messages": messages, "temperature": 0.7,
        "max_tokens": min(500, 60 * n + 60), "stream": False,
    }
    data = _http_json("POST", f"{base}/chat/completions", api_key, payload, timeout=120)
    return data["choices"][0]["message"]["content"]


# ============================================================
# Engine 2: local HuggingFace model
# ============================================================

_local = {"model": None, "tokenizer": None, "error": None}
_local_lock = threading.Lock()
_warm = {"started": False}


def _load_local():
    """Loads once; safe to call from a background thread and from a request at the same time."""
    with _local_lock:
        if _local["model"] is not None:
            return _local["model"], _local["tokenizer"]
        if _local["error"]:
            raise RuntimeError(_local["error"])
        try:
            import torch
            from transformers import AutoModelForCausalLM, AutoTokenizer
            name = _cfg()["local_model"]
            tokenizer = AutoTokenizer.from_pretrained(name)
            try:
                model = AutoModelForCausalLM.from_pretrained(name, dtype=torch.float32)
            except (TypeError, ValueError):                       # older transformers
                model = AutoModelForCausalLM.from_pretrained(name, torch_dtype=torch.float32)
            model.eval()
            _local.update(model=model, tokenizer=tokenizer)
            return model, tokenizer
        except Exception as exc:                                  # missing libs, no memory, no model files
            _local["error"] = f"{type(exc).__name__}: {exc}"
            raise RuntimeError(_local["error"])


def _generate_via_local(messages, n):
    model, tokenizer = _load_local()      # first: records a clear error if torch/transformers are missing
    import torch
    text = tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
    inputs = tokenizer(text, return_tensors="pt")
    with torch.inference_mode():
        out = model.generate(
            **inputs, max_new_tokens=min(300, 45 * n + 25), do_sample=True,
            temperature=0.7, top_p=0.9, pad_token_id=tokenizer.eos_token_id,
        )
    return tokenizer.decode(out[0][inputs["input_ids"].shape[1]:], skip_special_tokens=True)


def warm_up():
    """Start loading the local model in the background so the first 'Generate' click does not pay
    the load time. Does nothing when an LLM server is available or the local model is switched off."""
    if _warm["started"] or not _cfg()["use_local"] or _find_server() is not None:
        return
    _warm["started"] = True

    def _run():
        try:
            _load_local()
        except Exception:
            pass

    threading.Thread(target=_run, daemon=True).start()


# ============================================================
# Public API
# ============================================================

def describe_engine():
    """(label, detail, speed_note) for the UI, e.g. ('LM Studio', 'qwen3-4b', 'fast')."""
    server = _find_server()
    if server:
        base, model, _ = server
        label = "LM Studio" if ":1234" in base else ("Ollama" if ":11434" in base else "LLM API")
        return label, model, "fast"
    if _cfg()["use_local"] and not _local["error"]:
        state = "loaded" if _local["model"] is not None else "loads on first use"
        return "Local model", f"{_cfg()['local_model']}, {state}", "slow on CPU"
    return "Question bank", "", "instant, no AI"


def generate_questions_with_info(job_role, question_type="Technical", difficulty="Medium",
                                 num_questions=3, avoid=None):
    """Returns (questions, source). source is SOURCE_SERVER, SOURCE_LOCAL or SOURCE_BANK."""
    avoid = [a for a in (avoid or []) if a]
    messages = _messages(job_role, question_type, difficulty, num_questions, avoid)

    attempts = []
    server = _find_server()
    if server:
        attempts.append((SOURCE_SERVER, lambda: _generate_via_server(server, messages, num_questions)))
    if _cfg()["use_local"] and not _local["error"]:
        attempts.append((SOURCE_LOCAL, lambda: _generate_via_local(messages, num_questions)))

    for source, run in attempts:
        try:
            questions = _parse_questions(run())
        except Exception:
            if source == SOURCE_SERVER:
                _server_cache.update(checked_at=0.0, server=None)   # re-probe next time
            continue
        if questions:
            questions = questions[:num_questions]
            if len(questions) < num_questions:
                questions += _from_bank(job_role, question_type, num_questions - len(questions),
                                        exclude=questions + avoid)
            return questions, source

    return _from_bank(job_role, question_type, num_questions, exclude=avoid), SOURCE_BANK


def generate_questions(job_role, question_type="Technical", difficulty="Medium", num_questions=3):
    """Backwards-compatible: just the list of questions."""
    return generate_questions_with_info(job_role, question_type, difficulty, num_questions)[0]


if __name__ == "__main__":
    print("Engine:", describe_engine())
    for qtype in ["Technical", "Behavioral", "Aptitude"]:
        start = time.time()
        questions, source = generate_questions_with_info("Cloud Engineer", qtype, "Medium", 2)
        print(f"\n--- {qtype} ({source}, {time.time() - start:.1f}s) ---")
        for q in questions:
            print("-", q)