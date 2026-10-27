"""
interview_assistant_page.py
Recruiter/Admin UI for Milestone 3: create an interview session for a
candidate, generate role-specific questions (via interview_questions.py),
review/edit them, send the session to the candidate, and later view their
submitted answers. Wire into app.py -- see the integration note at the
bottom of this file.
"""

import secrets
from collections import Counter

import streamlit as st

from db import get_connection, insert_candidate_account
from auth import hash_password
from interview_db import (
    get_questions_for_session, mark_question_reviewed, update_question_text,
    set_session_status, get_sessions_for_recruiter, get_answers_for_session,
)
from interview_questions import describe_engine, warm_up
from generation_jobs import start_generation, get_job

DIFFICULTIES = ["Easy", "Medium", "Hard"]
QUESTION_TYPES = ["Technical", "Behavioral", "Aptitude"]


def _get_all_candidate_accounts():
    conn = get_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT id, name, email FROM candidate_accounts ORDER BY name")
    rows = cursor.fetchall()
    cursor.close()
    conn.close()
    return rows


def _job_panel_body(job_id):
    """Shows progress while the background job runs; once it finishes, stores the
    result and triggers one full re-run so polling stops and the Review tab
    picks up the new session."""
    job = get_job(job_id)
    if job is None:                                   # server restarted: nothing left to show
        st.session_state.pop("gen_job_id", None)
        return
    if job["status"] == "running":
        st.progress(job["step"] / max(job["total"], 1), text=f"{job['message']}...")
        st.caption(
            "This keeps running in the background. You can switch tabs or pages; "
            "the interview shows up under 'Review & Manage Sessions' when it is ready."
        )
        return
    st.session_state.pop("gen_job_id", None)
    st.session_state["gen_result"] = job
    st.rerun()


if hasattr(st, "fragment"):
    @st.fragment(run_every=2)
    def _job_panel(job_id):
        _job_panel_body(job_id)
else:                                                  # older Streamlit: manual refresh
    def _job_panel(job_id):
        _job_panel_body(job_id)
        if (get_job(job_id) or {}).get("status") == "running":
            st.button("Refresh status")


def _show_generation_result():
    job = st.session_state.get("gen_result")
    if not job:
        return
    if job["status"] == "error":
        st.error(f"Question generation failed: {job['error']}")
        return
    elapsed = (job["finished"] or job["started"]) - job["started"]
    mix = ", ".join(f"{n} {t}" for t, n in job["mix"].items())
    st.success(
        f"Interview created for {job['candidate_name']} in {elapsed:.0f}s: {mix} "
        f"({job['reused']} reused, {job['generated']} newly generated). "
        f"Open 'Review & Manage Sessions' to review and send it."
    )
    if job["used_bank"]:
        st.warning(
            "No AI engine was available for some questions, so ready-made questions were used. "
            "Start the LM Studio server (Developer tab) to get AI-written ones."
        )


def render_interview_assistant_page():
    warm_up()   # loads the local model in the background (no-op when LM Studio/Ollama is running)
    st.markdown("<div class='main-title'>Interview Assistant</div>", unsafe_allow_html=True)
    st.markdown(
        "<div class='subtitle'>Generate role-specific interview questions, "
        "review them, and check candidate answers</div>",
        unsafe_allow_html=True,
    )

    recruiter = st.session_state.get("recruiter")
    tab_create, tab_manage = st.tabs(["➕ Create Interview", "📋 Review & Manage Sessions"])

    # ------------------------------------------------------------------
    # TAB 1: create a new interview session
    # ------------------------------------------------------------------
    with tab_create:
        st.markdown("##### 1. Pick or add a candidate")

        candidates = _get_all_candidate_accounts()
        candidate_labels = {f"{c['name']} ({c['email']})": c for c in candidates}

        picked_label = st.selectbox(
            "Existing candidate account",
            ["-- create a new candidate account below --"] + list(candidate_labels.keys()),
        )

        selected_candidate = candidate_labels.get(picked_label)

        with st.expander("➕ Add a new candidate account"):
            with st.form("new_candidate_form", clear_on_submit=True):
                new_name = st.text_input("Candidate Name")
                new_email = st.text_input("Candidate Email")
                add_submitted = st.form_submit_button("Create Candidate Account")

            if add_submitted:
                clean_name = (new_name or "").strip()
                clean_email = (new_email or "").strip().lower()
                if not clean_name or not clean_email:
                    st.error("Please fill in both fields.")
                else:
                    temp_password = secrets.token_urlsafe(6)
                    salt, pwd_hash = hash_password(temp_password)
                    new_id = insert_candidate_account(clean_name, clean_email, salt, pwd_hash)
                    if new_id:
                        st.success(
                            f"Candidate account created. Share these login details with them:\n\n"
                            f"**Email:** {clean_email}  \n**Temporary password:** `{temp_password}`"
                        )
                    else:
                        st.error("An account with this email already exists.")

        st.markdown("---")
        st.markdown("##### 2. Interview details")

        job_role = st.text_input("Job Role", placeholder="e.g. Cloud Engineer")
        difficulty = st.selectbox("Difficulty", DIFFICULTIES, index=1)

        col1, col2, col3 = st.columns(3)
        with col1:
            n_technical = st.number_input("Technical questions", min_value=0, max_value=10, value=3)
        with col2:
            n_behavioral = st.number_input("Behavioral questions", min_value=0, max_value=10, value=2)
        with col3:
            n_aptitude = st.number_input("Aptitude questions", min_value=0, max_value=10, value=1)

        engine_label, engine_detail, engine_note = describe_engine()
        st.caption(
            f"AI engine: **{engine_label}**"
            + (f" ({engine_detail})" if engine_detail else "")
            + f", {engine_note}"
        )
        reuse = st.checkbox(
            "Reuse saved questions for this role and difficulty",
            value=True,
            help="Instant, and every candidate interviewing for the same role gets the same "
                 "questions. Untick to generate a fresh set.",
        )

        running = (get_job(st.session_state.get("gen_job_id")) or {}).get("status") == "running"
        generate = st.button("🚀 Generate Questions", type="primary", disabled=running)

        if generate:
            counts = {"Technical": n_technical, "Behavioral": n_behavioral, "Aptitude": n_aptitude}
            wanted = [(qtype, int(count)) for qtype, count in counts.items() if int(count) > 0]

            if not selected_candidate:
                st.error("Please select an existing candidate account first (or add one above).")
            elif not job_role.strip():
                st.error("Please enter a job role.")
            elif not wanted:
                st.error("Set at least one question count above zero.")
            else:
                st.session_state.pop("gen_result", None)
                st.session_state["gen_job_id"] = start_generation(
                    candidate_account_id=selected_candidate["id"],
                    candidate_name=selected_candidate["name"],
                    role=job_role.strip(),
                    difficulty=difficulty,
                    recruiter_id=recruiter["id"],
                    wanted=wanted,
                    reuse=reuse,
                )

        if st.session_state.get("gen_job_id"):
            _job_panel(st.session_state["gen_job_id"])
        else:
            _show_generation_result()

    # ------------------------------------------------------------------
    # TAB 2: review generated questions, send to candidate, view answers
    # ------------------------------------------------------------------
    with tab_manage:
        sessions = get_sessions_for_recruiter(recruiter["id"])

        if not sessions:
            st.info("No interview sessions yet — create one in the 'Create Interview' tab.")
            return

        session_labels = {
            f"{s['candidate_name']} — {s['job_role']} ({s['status']})": s for s in sessions
        }
        picked = st.selectbox("Select a session", list(session_labels.keys()))
        session = session_labels[picked]

        st.write(f"**Status:** {session['status']}  |  **Difficulty:** {session['difficulty']}")

        if session["status"] == "pending_review":
            st.markdown("##### Review questions before sending to candidate")
            questions = get_questions_for_session(session["id"])
            mix = Counter(q["question_type"] for q in questions)
            if mix:
                st.caption("Questions in this interview: " + ", ".join(f"{n} {t}" for t, n in mix.items()))

            all_reviewed = True
            for q in questions:
                with st.container(border=True):
                    st.write(f"**{q['question_type']}**")
                    new_text = st.text_area(
                        "Question", value=q["question_text"], key=f"qtext_{q['id']}", label_visibility="collapsed"
                    )
                    if new_text != q["question_text"]:
                        update_question_text(q["id"], new_text)

                    reviewed = st.checkbox(
                        "✅ Mark as reviewed", value=bool(q["reviewed"]), key=f"reviewed_{q['id']}"
                    )
                    if reviewed != bool(q["reviewed"]):
                        mark_question_reviewed(q["id"], reviewed)
                    if not reviewed:
                        all_reviewed = False

            st.markdown("---")
            if all_reviewed:
                if st.button("📤 Send to Candidate", type="primary"):
                    set_session_status(session["id"], "ready")
                    st.success("Sent! The candidate can now log in and take this interview.")
                    st.rerun()
            else:
                st.info("Mark every question as reviewed to enable sending.")

        elif session["status"] == "ready":
            st.info("Waiting for the candidate to complete this interview.")
            questions = get_questions_for_session(session["id"])
            for q in questions:
                st.write(f"- **[{q['question_type']}]** {q['question_text']}")

        elif session["status"] == "completed":
            st.markdown("##### Candidate's answers (visible only to you)")
            rows = get_answers_for_session(session["id"])
            for row in rows:
                with st.container(border=True):
                    st.write(f"**[{row['question_type']}]** {row['question_text']}")
                    if row["answer_text"]:
                        st.write(f"📝 *{row['answer_text']}*")
                    else:
                        st.write("_Not answered yet_")
                    if row.get("audio_data"):
                        st.caption("🎙️ Candidate's spoken answer:")
                        st.audio(row["audio_data"], format="audio/wav")


# ============================================================
# INTEGRATION INTO app.py
# ============================================================
# 1. At the top of app.py, add:
#        from interview_db import init_interview_tables
#        from interview_assistant_page import render_interview_assistant_page
#
# 2. Right after init_db(), add:
#        init_interview_tables()
#
# 3. In nav_options (both admin and recruiter should see this), add:
#        nav_options = [
#            "📄 Resume Upload",
#            "📊 Skills Analytics",
#            "👥 Candidates",
#            "🎤 Interview Assistant",   # <-- add this line
#        ]
#        if is_admin():
#            nav_options.append("🎯 Job Matching")
#
# 4. Add a routing branch (after the "👥 Candidates" elif block):
#        elif page == "🎤 Interview Assistant":
#            render_interview_assistant_page()