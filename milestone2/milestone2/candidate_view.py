"""
candidate_view.py
The candidate-facing screen (resume upload + interviews), rendered inside
the SAME app.py as recruiter/admin -- no separate script or port. Call
render_candidate_view() from app.py once you've confirmed
is_candidate_authenticated() is True.
"""

import os
import tempfile

import streamlit as st

from db import (
    insert_candidate, get_resume_for_candidate_account,
    get_all_jobs, apply_to_job, has_applied, get_applications_for_candidate,
)
from resume_parser import extract_text_from_file
from extractor import extract_fields
from interview_db import (
    get_sessions_for_candidate, get_questions_for_session,
    submit_answer, get_answer_for_question, set_session_status,
)
from login_page import render_candidate_logout_button
from voice_screening import render_voice_controls
from ui_theme import brand_html, page_header_html, render


def render_candidate_view():
    candidate = st.session_state["candidate"]

    with st.sidebar:
        st.markdown(brand_html(), unsafe_allow_html=True)
        render_candidate_logout_button()

    render(page_header_html(
        f"Welcome, {candidate['name']}",
        "Upload your resume, apply to open roles, and take the interviews recruiters send you."))

    tab_resume, tab_jobs, tab_interviews = st.tabs(["📄 My Resume", "💼 Job Openings", "🎤 My Interviews"])

    # ============================================================
    # TAB 1: resume upload
    # ============================================================
    with tab_resume:
        existing_resume = get_resume_for_candidate_account(candidate["id"])

        if existing_resume:
            st.success(
                "You've already uploaded a resume. Uploading a new one below will replace it."
            )
            st.write(f"**Name:** {existing_resume.get('name', 'Not found')}")
            st.write(f"**Skills:** {existing_resume.get('skills', 'Not found')}")
            st.write(f"**Experience:** {existing_resume.get('experience', 'Not found')}")
            st.markdown("---")

        st.markdown("##### Upload your resume (PDF or DOCX)")
        uploaded_file = st.file_uploader("Resume", type=["pdf", "docx"], label_visibility="collapsed")

        if uploaded_file and st.button("🚀 Parse & Save Resume", type="primary"):
            file_extension = os.path.splitext(uploaded_file.name)[1]
            file_bytes = uploaded_file.getvalue()
            with tempfile.NamedTemporaryFile(delete=False, suffix=file_extension) as temp_file:
                temp_file.write(file_bytes)
                temp_path = temp_file.name

            try:
                with st.spinner("Extracting information from your resume..."):
                    text = extract_text_from_file(temp_path)
                    profile = extract_fields(text, uploaded_file.name)
                    profile["candidate_account_id"] = candidate["id"]
                    profile["resume_file"] = file_bytes
                    profile["resume_file_name"] = uploaded_file.name
                    insert_candidate(profile)
                st.success("Resume uploaded! You can now apply to job openings in the next tab.")
                st.rerun()
            except Exception as e:
                st.error(f"Error while processing resume: {e}")
            finally:
                if os.path.exists(temp_path):
                    os.remove(temp_path)

    # ============================================================
    # TAB 2: job openings -- browse + apply
    # ============================================================
    with tab_jobs:
        resume = get_resume_for_candidate_account(candidate["id"])
        if not resume:
            st.warning("Upload your resume in the 'My Resume' tab first — you'll need it to apply.")
        else:
            jobs = get_all_jobs()
            if not jobs:
                st.info("No job openings posted yet. Check back later.")
            else:
                for job in jobs:
                    with st.container(border=True):
                        st.markdown(f"#### 💼 {job['title']}")
                        st.write(f"**Experience required:** {job.get('experience_required', 0)} years")
                        st.write(f"**Education required:** {job.get('education_required') or 'Not specified'}")
                        skills = job.get("required_skills") or []
                        if skills:
                            st.write("**Required Skills:** " + ", ".join(skills))

                        already_applied = has_applied(job["id"], candidate["id"])
                        if already_applied:
                            st.success("✅ You've already applied to this job.")
                        else:
                            if st.button(f"Apply with my uploaded resume", key=f"apply_{job['id']}"):
                                success = apply_to_job(job["id"], candidate["id"], resume["id"])
                                if success:
                                    st.success("Applied! The recruiter can now see your resume for this job.")
                                    st.rerun()
                                else:
                                    st.info("You've already applied to this job.")

    # ============================================================
    # TAB 3: interviews
    # ============================================================
    with tab_interviews:
        sessions = get_sessions_for_candidate(candidate["id"])

        if not sessions:
            st.info("No interviews assigned to you yet. Once a recruiter schedules one, it'll show up here.")
        else:
            session_labels = {
                f"{s['job_role']} ({s['difficulty']}) — {s['status']}": s for s in sessions
            }
            picked_label = st.selectbox("Select an interview", list(session_labels.keys()))
            session = session_labels[picked_label]

            st.markdown("---")

            if session["status"] == "completed":
                st.success("You've already completed this interview. Thanks!")
                questions = get_questions_for_session(session["id"])
                for q in questions:
                    answer = get_answer_for_question(q["id"])
                    with st.container(border=True):
                        st.write(f"**[{q['question_type']}]** {q['question_text']}")
                        st.write(f"Your answer: *{answer['answer_text'] if answer else '(none)'}*")
                        if answer and answer.get("audio_data"):
                            st.audio(answer["audio_data"], format="audio/wav")

            else:
                st.write(f"**Role:** {session['job_role']}  |  **Difficulty:** {session['difficulty']}")
                st.caption(
                    "For each question: optionally have it read aloud, record your spoken "
                    "answer or type it, then submit all when you're done."
                )

                questions = get_questions_for_session(session["id"])

                for q in questions:
                    answer_key = f"answer_{q['id']}"
                    audio_key = f"audio_{q['id']}"
                    if answer_key not in st.session_state:
                        existing = get_answer_for_question(q["id"])
                        st.session_state[answer_key] = existing["answer_text"] if existing else ""
                        st.session_state[audio_key] = existing.get("audio_data") if existing else None

                    with st.container(border=True):
                        st.markdown(f"**[{q['question_type']}]** {q['question_text']}")

                        render_voice_controls(q["id"], q["question_text"], answer_key, audio_key)

                        st.text_area(
                            "Your answer", key=answer_key, label_visibility="collapsed",
                        )

                submit_all = st.button("✅ Submit All Answers", type="primary")

                if submit_all:
                    empty = [q["id"] for q in questions if not st.session_state[f"answer_{q['id']}"].strip()]
                    if empty:
                        st.error("Please answer every question before submitting (type it if you didn't record).")
                    else:
                        for q in questions:
                            submit_answer(
                                q["id"],
                                st.session_state[f"answer_{q['id']}"].strip(),
                                audio_data=st.session_state.get(f"audio_{q['id']}"),
                            )
                        set_session_status(session["id"], "completed")
                        st.success("All answers submitted! Your recruiter will review them.")
                        st.rerun()