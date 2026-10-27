"""
job_matching_page.py
Milestone 2 UI: create job postings, run candidate-job matching, and view
hiring scores + skill-gap reports for every candidate. Wire this into
app.py -- see the three-line integration note at the bottom of this file.
"""

import streamlit as st
import pandas as pd

from job_parser import extract_job_requirements
from matching_engine import batch_match
from db import (
    insert_job, get_all_jobs,
    save_match_results, get_matches_for_job,
    get_all_candidates, get_applications_for_job,
)


def _score_badge(score: float) -> str:
    if score >= 85:
        color, bg, label = "#15803d", "#dcfce7", "Strong Match"
    elif score >= 60:
        color, bg, label = "#b45309", "#fef3c7", "Possible Match"
    else:
        color, bg, label = "#b91c1c", "#fee2e2", "Weak Match"
    return (
        f"<span style='background:{bg};color:{color};border-radius:15px;"
        f"padding:4px 12px;font-size:12px;font-weight:600;'>{score:.1f}% &middot; {label}</span>"
    )


def _skill_badges(skills, color="#eef2ff", text_color="#3730a3") -> str:
    if not skills:
        return "<span style='color:#667085;'>None</span>"
    return "".join(
        f"<span style='display:inline-block;background:{color};color:{text_color};"
        f"border-radius:15px;padding:4px 10px;margin:3px;font-size:12px;'>{s}</span>"
        for s in skills
    )


def render_job_matching_page():
    st.markdown("<div class='main-title'>Candidate-Job Matching & Skill Analysis</div>", unsafe_allow_html=True)
    st.markdown(
        "<div class='subtitle'>Match candidates against job requirements, "
        "calculate hiring scores, and generate skill-gap reports</div>",
        unsafe_allow_html=True,
    )

    tab_jobs, tab_match = st.tabs(["📋 Job Postings", "🎯 Run Matching"])

    # ------------------------------------------------------------------
    # TAB 1: create / view job postings
    # ------------------------------------------------------------------
    with tab_jobs:
        with st.form("new_job_form", clear_on_submit=True):
            st.markdown("##### Add a Job Posting")
            job_title = st.text_input(
                "Job Title (optional -- guessed from the description if left blank)"
            )
            job_description = st.text_area(
                "Paste the full job description",
                height=220,
                placeholder="e.g. We are looking for a Senior ML Engineer with 4+ years "
                            "of experience in Python, TensorFlow, AWS SageMaker...",
            )
            submitted = st.form_submit_button("➕ Add Job Posting", type="primary")

        if submitted:
            if not job_description or not job_description.strip():
                st.error("Please paste a job description first.")
            else:
                parsed = extract_job_requirements(job_description, title=job_title)
                insert_job(parsed)
                st.success(
                    f"Job posting '{parsed['title']}' added — "
                    f"{len(parsed['required_skills'])} required skills detected."
                )

        st.markdown("---")
        st.markdown("##### Existing Job Postings")

        jobs = get_all_jobs()
        if not jobs:
            st.info("No job postings yet. Add one above.")
        else:
            for job in jobs:
                with st.expander(f"💼 {job['title']}"):
                    col1, col2 = st.columns(2)
                    with col1:
                        st.write(f"**Experience required:** {job.get('experience_required', 0)} years")
                        st.write(f"**Education required:** {job.get('education_required') or 'Not specified'}")
                    with col2:
                        st.write("**Required Skills:**")
                        st.markdown(_skill_badges(job.get("required_skills") or []), unsafe_allow_html=True)

                    st.markdown("---")
                    st.markdown("**📥 Applicants**")
                    applicants = get_applications_for_job(job["id"])
                    if not applicants:
                        st.caption("No one has applied to this job yet.")
                    else:
                        for app in applicants:
                            acol1, acol2 = st.columns([3, 1])
                            with acol1:
                                st.write(f"**{app['name']}** &nbsp; {app['email']}", unsafe_allow_html=True)
                                st.caption(f"Applied: {app['applied_at']}")
                            with acol2:
                                if app.get("resume_file"):
                                    st.download_button(
                                        "⬇️ Resume",
                                        data=app["resume_file"],
                                        file_name=app.get("resume_file_name") or "resume",
                                        key=f"dl_{job['id']}_{app['application_id']}",
                                    )
                                else:
                                    st.caption("No file on record")

    # ------------------------------------------------------------------
    # TAB 2: run matching against all candidates
    # ------------------------------------------------------------------
    with tab_match:
        jobs = get_all_jobs()
        if not jobs:
            st.info("Add a job posting in the 'Job Postings' tab first.")
            return

        job_options = {job["title"]: job for job in jobs}
        selected_title = st.selectbox("Select a job posting to match against", list(job_options.keys()))
        selected_job = job_options[selected_title]

        run = st.button("🚀 Run Matching for All Candidates", type="primary")
        candidates = get_all_candidates()

        if run:
            if not candidates:
                st.warning("No candidates in the system yet — upload resumes first.")
            else:
                with st.spinner("Calculating hiring scores and skill gaps..."):
                    results_df = batch_match(candidates, selected_job)
                    save_match_results(selected_job["id"], results_df)
                st.success(f"Matched {len(results_df)} candidates against '{selected_job['title']}'.")

        stored = get_matches_for_job(selected_job["id"]) if selected_job.get("id") else []

        if stored:
            df = pd.DataFrame(stored)
            avg_score = df["hiring_score"].mean()
            strong_matches = int((df["hiring_score"] >= 85).sum())

            c1, c2, c3 = st.columns(3)
            with c1:
                st.markdown(
                    f"""<div class="stat-card"><div class="stat-label">Candidates Matched</div>
                    <div class="stat-value">{len(df)}</div></div>""",
                    unsafe_allow_html=True,
                )
            with c2:
                st.markdown(
                    f"""<div class="stat-card"><div class="stat-label">Avg Hiring Score</div>
                    <div class="stat-value">{avg_score:.1f}%</div></div>""",
                    unsafe_allow_html=True,
                )
            with c3:
                st.markdown(
                    f"""<div class="stat-card"><div class="stat-label">Strong Matches (&ge;85%)</div>
                    <div class="stat-value">{strong_matches}</div></div>""",
                    unsafe_allow_html=True,
                )

            st.markdown("<br>", unsafe_allow_html=True)
            st.markdown("##### Ranked Candidates")

            for _, row in df.sort_values("hiring_score", ascending=False).iterrows():
                st.markdown(
                    f"""<div class="candidate-row">
                    <div style="display:flex;justify-content:space-between;align-items:center;">
                    <div><b>{row['name']}</b> &nbsp;
                    <span style="color:#667085;font-size:13px;">{row.get('email', '')}</span></div>
                    {_score_badge(row['hiring_score'])}
                    </div>
                    </div>""",
                    unsafe_allow_html=True,
                )
                with st.expander(f"Skill-Gap Report — {row['name']}"):
                    st.write("**Matched Skills:**")
                    st.markdown(_skill_badges(row["matched_skills"]), unsafe_allow_html=True)
                    st.write("**Missing Skills:**")
                    st.markdown(
                        _skill_badges(row["missing_skills"], color="#fee2e2", text_color="#b91c1c"),
                        unsafe_allow_html=True,
                    )
                    if row["missing_skills"]:
                        st.write("**Recommendations:**")
                        for skill in row["missing_skills"]:
                            st.write(f"- Consider training in {skill}")
        else:
            st.info("Click 'Run Matching' to generate hiring scores and skill-gap reports for this job.")