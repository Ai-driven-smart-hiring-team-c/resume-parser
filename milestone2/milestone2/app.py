import streamlit as st

import settings
settings.bootstrap()   # Streamlit Cloud secrets -> environment variables, before db.py is imported

import pandas as pd
from collections import Counter

from resume_parser import process_resume
from db import init_db, get_all_candidates, get_candidate_count, delete_candidate
from job_matching_page import render_job_matching_page
from login_page import (
    is_recruiter_authenticated, is_candidate_authenticated, render_unified_login_page,
    render_logout_button, is_admin,
)
from interview_db import init_interview_tables
from interview_assistant_page import render_interview_assistant_page
from candidate_view import render_candidate_view
from dashboard_page import render_dashboard_page
from skill_gap_page import render_skill_gap_page
from ui_theme import inject_theme, brand_html


# ============================================================
# PAGE CONFIGURATION
# ============================================================

st.set_page_config(
    page_title="Recruitment Copilot",
    page_icon="💼",
    layout="wide"
)


# ============================================================
# DATABASE INITIALIZATION
# ============================================================

init_db()
init_interview_tables()


# ============================================================
# AUTHENTICATION GATE (unified: recruiter/admin OR candidate)
# ============================================================

if not is_recruiter_authenticated() and not is_candidate_authenticated():
    render_unified_login_page()
    st.stop()

# Global look (fonts, palette, sidebar, tabs, buttons) for every signed-in page
inject_theme()

# Candidate accounts get a completely separate, simpler view -- render it
# and stop before any of the recruiter/admin sidebar or pages below run.
if is_candidate_authenticated():
    render_candidate_view()
    st.stop()


# ============================================================
# CUSTOM CSS
# ============================================================

st.markdown(
    """
    <style>

    /* Main page */
    .main {
        background-color: #f5f7fb;
    }

    /* Hide Streamlit default menu */
    #MainMenu {
        visibility: hidden;
    }

    footer {
        visibility: hidden;
    }

    /* Main title */
    .main-title {
        font-size: 32px;
        font-weight: 700;
        color: #101828;
        margin-bottom: 5px;
    }

    .subtitle {
        color: #667085;
        font-size: 15px;
        margin-bottom: 25px;
    }

    /* Cards */
    .card {
        background: white;
        border: 1px solid #d9dee8;
        border-radius: 10px;
        padding: 20px;
        margin-bottom: 20px;
    }

    /* Section title */
    .section-title {
        font-size: 18px;
        font-weight: 700;
        color: #101828;
        margin-bottom: 15px;
    }

    /* Statistics */
    .stat-card {
        background: white;
        border: 1px solid #d9dee8;
        border-radius: 10px;
        padding: 22px;
        text-align: center;
        height: 130px;
    }

    .stat-label {
        color: #667085;
        font-size: 13px;
        text-transform: uppercase;
        letter-spacing: 0.5px;
    }

    .stat-value {
        font-size: 34px;
        font-weight: 700;
        color: #2563eb;
        margin-top: 8px;
    }

    /* Skill badges */
    .skill-badge {
        display: inline-block;
        background-color: #eef2ff;
        color: #3730a3;
        border-radius: 15px;
        padding: 5px 10px;
        margin: 3px;
        font-size: 12px;
    }

    /* Status */
    .status-pill {
        display: inline-block;
        background-color: #dcfce7;
        color: #15803d;
        border-radius: 15px;
        padding: 5px 12px;
        font-size: 12px;
        font-weight: 600;
    }

    /* Candidate rows */
    .candidate-row {
        background: white;
        border: 1px solid #e4e7ec;
        border-radius: 8px;
        padding: 15px;
        margin-bottom: 10px;
    }

    .candidate-label {
        color: #667085;
        font-size: 11px;
        text-transform: uppercase;
        margin-bottom: 3px;
    }

    .candidate-value {
        color: #101828;
        font-size: 14px;
    }

    /* Extracted information */
    .info-label {
        font-weight: 700;
        color: #101828;
    }

    .info-value {
        color: #344054;
    }

    /* Upload box */
    .upload-info {
        color: #667085;
        font-size: 13px;
        text-align: center;
    }

    </style>
    """,
    unsafe_allow_html=True
)


# ============================================================
# HELPER FUNCTIONS
# ============================================================

def parse_skills(skills):
    """
    Convert skills stored in database into a Python list.
    Supports comma-separated strings.
    """

    if not skills:
        return []

    if isinstance(skills, list):
        return skills

    return [
        skill.strip()
        for skill in str(skills).split(",")
        if skill.strip()
    ]


def get_skill_statistics(candidates):
    """
    Calculate:
    - unique skills
    - total occurrences
    - top skills
    """

    counter = Counter()

    for candidate in candidates:
        skills = parse_skills(candidate.get("skills"))

        for skill in skills:
            counter[skill] += 1

    return counter


def display_skill_badges(skills):
    """
    Display skills as small badges.
    """

    if not skills:
        st.write("Not found")
        return

    html = ""

    for skill in skills:
        html += f"<span class='skill-badge'>{skill}</span>"

    st.markdown(html, unsafe_allow_html=True)


# ============================================================
# SIDEBAR
# ============================================================

with st.sidebar:

    st.markdown(brand_html(), unsafe_allow_html=True)

    render_logout_button()

    # Job Matching (job postings) is admin-only -- recruiters don't get it
    nav_options = [
        "📊 Dashboard",
        "📄 Resume Upload",
        "📊 Skills Analytics",
        "👥 Candidates",
        "🧩 Skill Gap Analysis",
        "🎤 Interview Assistant",
    ]
    if is_admin():
        nav_options.append("🎯 Job Matching")

    page = st.radio(
        "Navigation",
        nav_options
    )

    st.markdown("---")

    st.markdown("### Quick Stats")

    candidates = get_all_candidates()

    st.write(f"**Candidates:** {len(candidates)}")

    skill_counter = get_skill_statistics(candidates)

    st.write(f"**Unique Skills:** {len(skill_counter)}")

    if candidates:
        average_skills = sum(
            len(parse_skills(c.get("skills")))
            for c in candidates
        ) / len(candidates)
    else:
        average_skills = 0

    st.write(f"**Avg Skills:** {average_skills:.1f}")


# ============================================================
# DASHBOARD PAGE (Milestone 4)
# ============================================================

if page == "📊 Dashboard":

    render_dashboard_page()


# ============================================================
# RESUME UPLOAD PAGE
# ============================================================

elif page == "📄 Resume Upload":

    st.markdown(
        "<div class='main-title'>Resume Parsing & Candidate Profiling</div>",
        unsafe_allow_html=True
    )

    st.markdown(
        "<div class='subtitle'>"
        "Upload and process resumes to create structured candidate profiles"
        "</div>",
        unsafe_allow_html=True
    )


    # --------------------------------------------------------
    # TOP TWO CARDS
    # --------------------------------------------------------

    left, right = st.columns([1, 1])


    # ========================================================
    # UPLOAD CARD
    # ========================================================

    with left:

        st.markdown(
            """
            <div class="card">

            <div class="section-title">
                📄 Upload Resume
            </div>

            <div class="upload-info">
                Supported formats: PDF, DOCX
            </div>

            </div>
            """,
            unsafe_allow_html=True
        )

        uploaded_file = st.file_uploader(
            "Upload",
            type=["pdf", "docx"],
            label_visibility="collapsed"
        )


    # ========================================================
    # PARSING PROGRESS
    # ========================================================

    with right:

        st.markdown(
            """
            <div class="card">

            <div class="section-title">
                📊 Parsing Progress
            </div>

            """,
            unsafe_allow_html=True
        )

        progress_value = 0

        if uploaded_file:
            progress_value = 95

        st.write(
            f"Extraction Progress                      {progress_value}%"
        )

        st.progress(progress_value / 100)

        total_candidates = get_candidate_count()

        col1, col2, col3 = st.columns(3)

        with col1:
            st.metric(
                "Resumes Processed",
                total_candidates
            )

        with col2:
            st.metric(
                "Extraction Accuracy",
                "—"
            )

        with col3:
            st.metric(
                "Profiles Created",
                total_candidates
            )

        st.markdown("</div>", unsafe_allow_html=True)


    # ========================================================
    # PROCESS UPLOADED FILE
    # ========================================================

    if uploaded_file:

        st.markdown("---")

        st.subheader("📄 Uploaded Resume")

        st.write(
            f"**File:** {uploaded_file.name}"
        )

        # Save uploaded file temporarily
        import tempfile
        import os

        file_extension = os.path.splitext(
            uploaded_file.name
        )[1]

        with tempfile.NamedTemporaryFile(
            delete=False,
            suffix=file_extension
        ) as temp_file:

            temp_file.write(
                uploaded_file.getbuffer()
            )

            temp_path = temp_file.name


        if st.button(
            "🚀 Parse Resume",
            type="primary"
        ):

            try:

                with st.spinner(
                    "Extracting information from resume..."
                ):

                    profile = process_resume(
                        temp_path,
                        uploaded_file.name
                    )

                st.success(
                    "Resume processed successfully!"
                )

                # Store latest profile
                st.session_state["latest_profile"] = profile

            except Exception as e:

                st.error(
                    f"Error while processing resume: {e}"
                )

            finally:

                if os.path.exists(temp_path):
                    os.remove(temp_path)


    # ========================================================
    # EXTRACTED INFORMATION
    # ========================================================

    if "latest_profile" in st.session_state:

        profile = st.session_state["latest_profile"]

        st.markdown(
            """
            <div class="card">
            <div class="section-title">
                🔍 Extracted Information
            </div>
            """,
            unsafe_allow_html=True
        )

        col1, col2 = st.columns(2)

        with col1:

            st.markdown(
                f"""
                <p>
                <span class="info-label">Name:</span>
                <span class="info-value">
                {profile.get("name", "Not found")}
                </span>
                </p>

                <p>
                <span class="info-label">Phone:</span>
                <span class="info-value">
                {profile.get("phone", "Not found")}
                </span>
                </p>

                <p>
                <span class="info-label">Education:</span>
                <span class="info-value">
                {profile.get("education", "Not found")}
                </span>
                </p>

                <p>
                <span class="info-label">Location:</span>
                <span class="info-value">
                {profile.get("location", "Not found")}
                </span>
                </p>
                """,
                unsafe_allow_html=True
            )


        with col2:

            email = profile.get(
                "email",
                "Not found"
            )

            st.markdown(
                f"""
                <p>
                <span class="info-label">Email:</span>
                <span class="info-value">
                {email}
                </span>
                </p>

                <p>
                <span class="info-label">Experience:</span>
                <span class="info-value">
                {profile.get("experience", "Not found")}
                </span>
                </p>

                <p>
                <span class="info-label">Certifications:</span>
                <span class="info-value">
                {profile.get("certifications", "Not found")}
                </span>
                </p>
                """,
                unsafe_allow_html=True
            )


        st.markdown("### Skills")

        skills = parse_skills(
            profile.get("skills")
        )

        display_skill_badges(skills)


        st.markdown("### Summary")

        st.write(
            profile.get(
                "summary",
                "Not found"
            )
        )

        st.markdown("</div>", unsafe_allow_html=True)


    # ========================================================
    # RECENTLY PROCESSED CANDIDATES
    # ========================================================

    st.markdown("---")

    st.markdown(
        """
        <div class="section-title">
            👥 Recently Processed Candidates
        </div>
        """,
        unsafe_allow_html=True
    )

    candidates = get_all_candidates()

    if candidates:

        # Header
        header = st.columns(
            [1.2, 1.6, 1, 3, 0.8]
        )

        headers = [
            "Candidate Name",
            "Email",
            "Experience",
            "Key Skills",
            "Status"
        ]

        for column, title in zip(
            header,
            headers
        ):

            with column:

                st.markdown(
                    f"""
                    <div class="candidate-label">
                    {title}
                    </div>
                    """,
                    unsafe_allow_html=True
                )


        # Candidate rows
        for candidate in candidates[:10]:

            cols = st.columns(
                [1.2, 1.6, 1, 3, 0.8]
            )

            name = candidate.get(
                "name"
            ) or "Not found"

            email = candidate.get(
                "email"
            ) or "Not found"

            experience = candidate.get(
                "experience"
            ) or "Not found"

            skills = parse_skills(
                candidate.get("skills")
            )


            with cols[0]:

                st.markdown(
                    f"""
                    <div class="candidate-row">

                    <div class="candidate-value">
                    <b>{name}</b>
                    </div>

                    </div>
                    """,
                    unsafe_allow_html=True
                )


            with cols[1]:

                st.markdown(
                    f"""
                    <div class="candidate-row">

                    <div class="candidate-value">
                    {email}
                    </div>

                    </div>
                    """,
                    unsafe_allow_html=True
                )


            with cols[2]:

                st.markdown(
                    f"""
                    <div class="candidate-row">

                    <div class="candidate-value">
                    {experience}
                    </div>

                    </div>
                    """,
                    unsafe_allow_html=True
                )


            with cols[3]:

                skill_html = ""

                if skills:

                    for skill in skills:

                        skill_html += (
                            f"<span class='skill-badge'>"
                            f"{skill}"
                            f"</span>"
                        )

                else:

                    skill_html = "Not found"


                st.markdown(
                    f"""
                    <div class="candidate-row">
                    {skill_html}
                    </div>
                    """,
                    unsafe_allow_html=True
                )


            with cols[4]:

                st.markdown(
                    """
                    <div class="candidate-row">

                    <span class="status-pill">
                    Processed
                    </span>

                    </div>
                    """,
                    unsafe_allow_html=True
                )

    else:

        st.info(
            "No candidates processed yet."
        )


# ============================================================
# SKILLS ANALYTICS PAGE
# ============================================================

elif page == "📊 Skills Analytics":

    st.markdown(
        "<div class='main-title'>Skills Analytics</div>",
        unsafe_allow_html=True
    )

    st.markdown(
        "<div class='subtitle'>"
        "Analyze the skills extracted from all candidate resumes"
        "</div>",
        unsafe_allow_html=True
    )


    candidates = get_all_candidates()

    skill_counter = get_skill_statistics(
        candidates
    )


    # ========================================================
    # TOP STATISTICS
    # ========================================================

    unique_skills = len(skill_counter)

    total_occurrences = sum(
        skill_counter.values()
    )

    if skill_counter:

        top_skill = skill_counter.most_common(1)[0][0]

    else:

        top_skill = "—"


    col1, col2, col3 = st.columns(3)


    with col1:

        st.markdown(
            f"""
            <div class="stat-card">

            <div class="stat-label">
            Total Unique Skills
            </div>

            <div class="stat-value">
            {unique_skills}
            </div>

            </div>
            """,
            unsafe_allow_html=True
        )


    with col2:

        st.markdown(
            f"""
            <div class="stat-card">

            <div class="stat-label">
            Top Skill
            </div>

            <div class="stat-value">
            {top_skill}
            </div>

            </div>
            """,
            unsafe_allow_html=True
        )


    with col3:

        st.markdown(
            f"""
            <div class="stat-card">

            <div class="stat-label">
            Total Occurrences
            </div>

            <div class="stat-value">
            {total_occurrences}
            </div>

            </div>
            """,
            unsafe_allow_html=True
        )


    st.markdown("<br>", unsafe_allow_html=True)


    # ========================================================
    # TOP 20 SKILLS
    # ========================================================

    left, right = st.columns(2)


    with left:

        st.subheader("📊 Top 20 Skills")

        if skill_counter:

            top20 = skill_counter.most_common(20)

            df_top20 = pd.DataFrame(
                top20,
                columns=[
                    "Skill",
                    "Count"
                ]
            )

            df_top20 = df_top20.set_index(
                "Skill"
            )

            st.bar_chart(
                df_top20,
                horizontal=True,
                height=500
            )

        else:

            st.info(
                "No skill data available."
            )


    # ========================================================
    # SKILL DISTRIBUTION TOP 5
    # ========================================================

    with right:

        st.subheader(
            "🥧 Skill Distribution (Top 5)"
        )

        if skill_counter:

            top5 = skill_counter.most_common(5)

            labels = [
                item[0]
                for item in top5
            ]

            values = [
                item[1]
                for item in top5
            ]

            total_top5 = sum(values)

            for skill, count in top5:

                percentage = (
                    count /
                    total_top5 *
                    100
                )

                st.markdown(
                    f"""
                    <div style="
                        margin-bottom:15px;
                    ">

                    <div style="
                        display:flex;
                        justify-content:space-between;
                        margin-bottom:5px;
                    ">

                    <span>
                    <b>{skill}</b>
                    </span>

                    <span>
                    {count} ({percentage:.1f}%)
                    </span>

                    </div>

                    <div style="
                        background:#e5e7eb;
                        border-radius:8px;
                        height:12px;
                    ">

                    <div style="
                        width:{percentage}%;
                        background:#4f46e5;
                        height:12px;
                        border-radius:8px;
                    ">
                    </div>

                    </div>

                    </div>
                    """,
                    unsafe_allow_html=True
                )

        else:

            st.info(
                "No skill data available."
            )


# ============================================================
# CANDIDATES PAGE
# ============================================================

elif page == "👥 Candidates":

    st.markdown(
        "<div class='main-title'>Candidate Directory</div>",
        unsafe_allow_html=True
    )

    st.markdown(
        "<div class='subtitle'>"
        "View all processed candidates"
        "</div>",
        unsafe_allow_html=True
    )


    candidates = get_all_candidates()


    if candidates:

        for candidate in candidates:

            name = candidate.get(
                "name"
            ) or "Not found"

            email = candidate.get(
                "email"
            ) or "Not found"

            phone = candidate.get(
                "phone"
            ) or "Not found"

            location = candidate.get(
                "location"
            ) or "Not found"

            education = candidate.get(
                "education"
            ) or "Not found"

            experience = candidate.get(
                "experience"
            ) or "Not found"

            skills = parse_skills(
                candidate.get("skills")
            )

            with st.expander(
                f"👤 {name}"
            ):

                col1, col2 = st.columns(2)

                with col1:

                    st.write(
                        f"**Email:** {email}"
                    )

                    st.write(
                        f"**Phone:** {phone}"
                    )

                    st.write(
                        f"**Location:** {location}"
                    )

                    st.write(
                        f"**Education:** {education}"
                    )

                with col2:

                    st.write(
                        f"**Experience:** {experience}"
                    )

                    st.write(
                        "**Skills:**"
                    )

                    display_skill_badges(
                        skills
                    )

                if is_admin():
                    st.markdown("---")
                    if st.button(f"🗑️ Delete this candidate", key=f"delete_candidate_{candidate['id']}"):
                        delete_candidate(candidate["id"])
                        st.success(f"Deleted {name}.")
                        st.rerun()

    else:

        st.info(
            "No candidates found."
        )


# ============================================================
# SKILL GAP ANALYSIS PAGE
# ============================================================

elif page == "🧩 Skill Gap Analysis":

    render_skill_gap_page()


# ============================================================
# INTERVIEW ASSISTANT PAGE (Milestone 3)
# ============================================================

elif page == "🎤 Interview Assistant":

    render_interview_assistant_page()


# ============================================================
# JOB MATCHING PAGE (Milestone 2) -- admin only
# ============================================================

elif page == "🎯 Job Matching":

    render_job_matching_page()