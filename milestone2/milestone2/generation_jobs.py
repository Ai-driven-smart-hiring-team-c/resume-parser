"""
generation_jobs.py
Runs interview-question generation in a background thread.

Why: Streamlit re-runs the whole page script on every click, and a re-run
cancels whatever the script was doing. A slow generation (several question
types, local model) used to be cut off half-way, leaving a session with only the
first type. A background thread is not affected by re-runs.

The interview session is created only after ALL question types are ready, so a
failed or interrupted job never leaves a half-filled session behind.

No Streamlit calls in here: worker threads have no script context.
"""

import threading
import time
import uuid

_JOBS = {}
_LOCK = threading.Lock()
_MAX_JOBS = 50


def _update(job_id, **fields):
    with _LOCK:
        if job_id in _JOBS:
            _JOBS[job_id].update(fields)


def get_job(job_id):
    """A snapshot copy of the job (safe to read while the worker keeps writing), or None."""
    if not job_id:
        return None
    with _LOCK:
        job = _JOBS.get(job_id)
        return dict(job) if job else None


def start_generation(*, candidate_account_id, candidate_name, role, difficulty,
                     recruiter_id, wanted, reuse):
    """wanted: list of (question_type, count). Returns the job id immediately."""
    job_id = uuid.uuid4().hex[:12]
    job = {
        "id": job_id, "status": "running", "step": 0, "total": len(wanted),
        "message": "Starting", "candidate_name": candidate_name, "role": role,
        "difficulty": difficulty, "session_id": None, "mix": {}, "reused": 0,
        "generated": 0, "used_bank": False, "error": None,
        "started": time.time(), "finished": None,
    }
    with _LOCK:
        _JOBS[job_id] = job
        for old_id in sorted(_JOBS, key=lambda j: _JOBS[j]["started"])[:-_MAX_JOBS]:
            _JOBS.pop(old_id, None)

    threading.Thread(
        target=_run,
        args=(job_id, candidate_account_id, role, difficulty, recruiter_id, list(wanted), reuse),
        daemon=True,
    ).start()
    return job_id


def _run(job_id, candidate_account_id, role, difficulty, recruiter_id, wanted, reuse):
    # imported here so the module itself stays importable/testable without a database
    from interview_db import (
        create_interview_session, add_question, get_cached_questions, save_cached_questions,
    )
    from interview_questions import generate_questions_with_info, SOURCE_BANK

    try:
        collected = []            # [(question_type, [question, ...])]
        reused_total = generated_total = 0
        used_bank = False

        for step, (qtype, count) in enumerate(wanted):
            _update(job_id, step=step, message=f"{qtype} questions ({step + 1} of {len(wanted)})")
            questions = get_cached_questions(role, qtype, difficulty, count) if reuse else []
            reused_total += len(questions)

            missing = count - len(questions)
            if missing > 0:
                new_questions, source = generate_questions_with_info(
                    role, qtype, difficulty, missing, avoid=questions
                )
                if source == SOURCE_BANK:
                    used_bank = True
                else:             # only AI-written questions are worth keeping for reuse
                    save_cached_questions(role, qtype, difficulty, new_questions, source)
                generated_total += len(new_questions)
                questions = questions + new_questions
            collected.append((qtype, questions))

        _update(job_id, step=len(wanted), message="Saving the interview")
        session_id = create_interview_session(candidate_account_id, role, difficulty, recruiter_id)
        order = 0
        for qtype, questions in collected:
            for text in questions:
                add_question(session_id, text, qtype, order)
                order += 1

        _update(
            job_id, status="done", session_id=session_id, reused=reused_total,
            generated=generated_total, used_bank=used_bank, message="Done",
            mix={qtype: len(qs) for qtype, qs in collected}, finished=time.time(),
        )
    except Exception as exc:      # report it to the UI instead of dying silently
        _update(job_id, status="error", error=f"{type(exc).__name__}: {exc}",
                message="Failed", finished=time.time())