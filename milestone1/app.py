import streamlit as st
import os
import tempfile
from collections import Counter

from resume_parser import process_resume
from db import init_db, get_all_candidates, get_candidate_count


# ============================================================
# PAGE CONFIG
# ============================================================

st.set_page_config(
    page_title="Recruitment Copilot",
    page_icon="📄",
    layout="wide",
    initial_sidebar_state="expanded"
)


# ============================================================
# CUSTOM CSS
# ============================================================

st.markdown("""
<style>

    /* Main page */
    .main {
        background-color: #f5f7fb;
    }

    /* Remove excessive top padding */
    .block-container {
        padding-top: 2rem;
        padding-bottom: 3rem;
        max-width: 1400px;
    }

    /* Sidebar */
    section[data-testid="stSidebar"] {
        background-color: #ffffff;
        border-right: 1px solid #e5e7eb;
    }

    /* Main heading */
    .main-title {
        font-size: 2rem;
        font-weight: 700;
        color: #111827;
        margin-bottom: 5px;
    }

    .subtitle {
        color: #64748b;
        font-size: 1rem;
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

    .card-title {
        font-size: 1.05rem;
        font-weight: 700;
        color: #111827;
        margin-bottom: 15px;
    }

    /* Metric cards */
    .metric-card {
        background: white;
        border: 1px solid #d9dee8;
        border-radius: 10px;
        padding: 22px;
        text-align: center;
        min-height: 140px;
    }

    .metric-label {
        color: #64748b;
        font-size: 0.85rem;
        font-weight: 600;
        text-transform: uppercase;
        letter-spacing: 0.5px;
    }

    .metric-value {
        color: #2563eb;
        font-size: 2.3rem;
        font-weight: 700;
        margin-top: 10px;
    }

    /* Skill badges */
    .skill-badge {
        display: inline-block;
        background: #eef2ff;
        color: #4338ca;
        border-radius: 15px;
        padding: 5px 10px;
        margin: 3px;
        font-size: 0.78rem;
        border: 1px solid #e0e7ff;
    }

    /* Status */
    .status-pill {
        display: inline-block;
        background: #dcfce7;
        color: #15803d;
        border-radius: 15px;
        padding: 5px 12px;
        font-size: 0.8rem;
        font-weight: 600;
    }

    /* Upload box */
    .upload-info {
        background: #f8fafc;
        border: 2px dashed #cbd5e1;
        border-radius: 10px;
        padding: 15px;
        text-align: center;
        color: #64748b;
    }

    /* Candidate information */
    .info-label {
        font-weight: 700;
        color: #111827;
    }

    .info-value {
        color: #334155;
    }

    /* Bar chart */
    .bar-container {
        margin: 8px 0;
    }

    .bar-label {
        display: flex;
        justify-content: space-between;
        margin-bottom: 4px;
        font-size: 0.85rem;
        color: #334155;
    }

    .bar-background {
        width: 100%;
        height: 18px;
        background: #e5e7eb;
        border-radius: 5px;
        overflow: hidden;
    }

    .bar-fill {
        height: 100%;
        background: #6366f1;
        border-radius: 5px;
    }

    /* Pie chart */
    .pie-wrapper {
        display: flex;
        justify-content: center;
        align-items: center;
        gap: 30px;
        padding: 10px;
    }

    .pie-chart {
        width: 230px;
        height: 230px;
        border-radius: 50%;
    }

    .legend-item {
        display: flex;
        align-items: center;
        margin: 8px 0;
        font-size: 0.85rem;
        color: #334155;
    }

    .legend-box {
        width: 13px;
        height: 13px;
        border-radius: 3px;
        margin-right: 8px;
    }

</style>
""", unsafe_allow_html=True)


# ============================================================
# DATABASE INITIALIZATION
# ============================================================

try:
    init_db()
except Exception as e:
    st.error(f"Database connection error: {e}")
    st.stop()


# ============================================================
# SIDEBAR
# ============================================================

with st.sidebar:

    st.markdown(
        """
        <div style="
            background:#6366f1;
            color:white;
            padding:12px;
            border-radius:10px;
            text-align:center;
            font-weight:700;
            margin-bottom:25px;
        ">
            📄 Recruitment Copilot
        </div>
        """,
        unsafe_allow_html=True
    )

    st.markdown("### Navigation")

    page = st.radio(
        "",
        [
            "📄 Resume Upload",
            "👥 Candidates",
            "📊 Skills Analytics"
        ],
        label_visibility="collapsed"
    )

    st.markdown("---")

    # Quick statistics
    try:
        total_candidates = get_candidate_count()
        candidates = get_all_candidates()
    except Exception:
        total_candidates = 0
        candidates = []

    st.markdown("### Quick Stats")

    st.write(f"**Candidates:** {total_candidates}")

    all_skills_sidebar = []

    for candidate in candidates:

        skills = candidate.get("skills", "")

        if skills:
            if isinstance(skills, list):
                all_skills_sidebar.extend(skills)
            else:
                for skill in str(skills).split(","):
                    skill = skill.strip()
                    if skill:
                        all_skills_sidebar.append(skill)

    unique_sidebar_skills = len(set(
        skill.lower() for skill in all_skills_sidebar
    ))

    st.write(f"**Unique Skills:** {unique_sidebar_skills}")

    if total_candidates > 0:
        avg_skills = len(all_skills_sidebar) / total_candidates
    else:
        avg_skills = 0

    st.write(f"**Avg Skills:** {avg_skills:.1f}")


# ============================================================
# HELPER FUNCTIONS
# ============================================================

def get_skill_list(candidate):
    """
    Convert candidate skills into a Python list.
    """

    skills = candidate.get("skills", "")

    if not skills:
        return []

    if isinstance(skills, list):
        return [str(x).strip() for x in skills if str(x).strip()]

    return [
        skill.strip()
        for skill in str(skills).split(",")
        if skill.strip()
    ]


def get_all_skills(candidates):
    """
    Get all skills from all candidates.
    """

    all_skills = []

    for candidate in candidates:
        all_skills.extend(get_skill_list(candidate))

    return all_skills


def normalize_skills(skills):
    """
    Combine skills such as Python/python/PYTHON.
    """

    skill_counter = Counter()

    display_names = {}

    for skill in skills:

        clean_skill = skill.strip()

        if not clean_skill:
            continue

        key = clean_skill.lower()

        skill_counter[key] += 1

        if key not in display_names:
            display_names[key] = clean_skill

    final_counter = Counter()

    for key, count in skill_counter.items():
        final_counter[display_names[key]] = count

    return final_counter


def display_skills(skills):
    """
    Display skill badges.
    """

    if not skills:
        return "Not found"

    html = ""

    for skill in skills:
        html += f"<span class='skill-badge'>{skill}</span>"

    return html


# ============================================================
# RESUME UPLOAD PAGE
# ============================================================

if page == "📄 Resume Upload":

    st.markdown(
        '<div class="main-title">Resume Parsing & Candidate Profiling</div>',
        unsafe_allow_html=True
    )

    st.markdown(
        '<div class="subtitle">Upload and process resumes to create structured candidate profiles</div>',
        unsafe_allow_html=True
    )

    # --------------------------------------------------------
    # TWO COLUMN LAYOUT
    # --------------------------------------------------------

    left_col, right_col = st.columns([1, 1])

    # ========================================================
    # LEFT - UPLOAD
    # ========================================================

    with left_col:

        st.markdown(
            """
            <div class="card">
                <div class="card-title">📄 Upload Resume</div>
            </div>
            """,
            unsafe_allow_html=True
        )

        uploaded_file = st.file_uploader(
            "Upload Resume",
            type=["pdf", "docx"],
            label_visibility="collapsed"
        )

        if uploaded_file:

            st.markdown(
                f"""
                <div class="upload-info">
                    📄 <b>{uploaded_file.name}</b><br>
                    <small>
                        {uploaded_file.size / 1024:.1f} KB • Uploaded just now
                    </small>
                </div>
                """,
                unsafe_allow_html=True
            )

            st.write("")

            process_button = st.button(
                "🚀 Parse Resume",
                type="primary",
                use_container_width=True
            )

            if process_button:

                progress = st.progress(0)

                try:

                    progress.progress(25)

                    # Temporary file
                    suffix = os.path.splitext(
                        uploaded_file.name
                    )[1]

                    with tempfile.NamedTemporaryFile(
                        delete=False,
                        suffix=suffix
                    ) as temp_file:

                        temp_file.write(
                            uploaded_file.getbuffer()
                        )

                        temp_path = temp_file.name

                    progress.progress(50)

                    # Process resume
                    profile = process_resume(
                        temp_path,
                        uploaded_file.name
                    )

                    progress.progress(100)

                    st.success(
                        "Resume processed successfully!"
                    )

                    # Save result in session
                    st.session_state["last_profile"] = profile

                    # Remove temporary file
                    try:
                        os.remove(temp_path)
                    except Exception:
                        pass

                except Exception as e:

                    progress.empty()

                    st.error(
                        f"Error processing resume: {e}"
                    )

        else:

            st.markdown(
                """
                <div class="upload-info">
                    Supported formats: <b>PDF, DOCX</b><br>
                    Maximum file size: 200 MB
                </div>
                """,
                unsafe_allow_html=True
            )

    # ========================================================
    # RIGHT - PARSING PROGRESS
    # ========================================================

    with right_col:

        candidates = get_all_candidates()

        total = len(candidates)

        st.markdown(
            """
            <div class="card">
                <div class="card-title">📊 Parsing Progress</div>
            </div>
            """,
            unsafe_allow_html=True
        )

        # If resume uploaded, show 100%, otherwise 0%
        if uploaded_file:
            progress_value = 95
        else:
            progress_value = 0

        st.write(
            f"Extraction Progress "
            f"<span style='float:right'>{progress_value}%</span>",
            unsafe_allow_html=True
        )

        st.progress(progress_value / 100)

        st.write("")

        # Mini statistics
        stat1, stat2, stat3 = st.columns(3)

        with stat1:

            st.markdown(
                f"""
                <div style="text-align:center">
                    <div style="font-size:0.85rem;color:#64748b">
                        Resumes<br>Processed
                    </div>
                    <div style="font-size:2rem;color:#2563eb;font-weight:700">
                        {total}
                    </div>
                </div>
                """,
                unsafe_allow_html=True
            )

        with stat2:

            st.markdown(
                """
                <div style="text-align:center">
                    <div style="font-size:0.85rem;color:#64748b">
                        Extraction<br>Accuracy
                    </div>
                    <div style="font-size:2rem;color:#334155;font-weight:700">
                        —
                    </div>
                </div>
                """,
                unsafe_allow_html=True
            )

        with stat3:

            st.markdown(
                f"""
                <div style="text-align:center">
                    <div style="font-size:0.85rem;color:#64748b">
                        Profiles<br>Created
                    </div>
                    <div style="font-size:2rem;color:#2563eb;font-weight:700">
                        {total}
                    </div>
                </div>
                """,
                unsafe_allow_html=True
            )

        st.divider()

        # ====================================================
        # EXTRACTED INFORMATION
        # ====================================================

        st.markdown(
            "### Extracted Information"
        )

        profile = st.session_state.get(
            "last_profile"
        )

        if profile:

            info1, info2 = st.columns(2)

            with info1:

                st.markdown(
                    f"""
                    **Name:** {profile.get("name") or "Not found"}

                    **Phone:** {profile.get("phone") or "Not found"}

                    **Education:** {profile.get("education") or "Not found"}

                    **Location:** {profile.get("location") or "Not found"}
                    """,
                    unsafe_allow_html=True
                )

            with info2:

                email = profile.get("email") or "Not found"

                st.markdown(
                    f"""
                    **Email:** {email}

                    **Experience:** {profile.get("experience") or "Not found"}

                    **Certifications:** {profile.get("certifications") or "Not found"}
                    """,
                    unsafe_allow_html=True
                )

            st.markdown("**Skills:**")

            skills = get_skill_list(profile)

            st.markdown(
                display_skills(skills),
                unsafe_allow_html=True
            )

            st.markdown("**Summary:**")

            st.info(
                profile.get("summary")
                or "No summary found."
            )

        else:

            st.info(
                "Upload a resume to see extracted fields here."
            )


    # ========================================================
    # RECENTLY PROCESSED CANDIDATES
    # ========================================================

    st.markdown("---")

    st.markdown(
        """
        <div class="card-title">
            👥 Recently Processed Candidates
        </div>
        """,
        unsafe_allow_html=True
    )

    candidates = get_all_candidates()

    if candidates:

        # Show newest first
        for candidate in candidates[:10]:

            name = candidate.get(
                "name"
            ) or "Not found"

            email = candidate.get(
                "email"
            ) or "Not found"

            experience = candidate.get(
                "experience"
            ) or "Not found"

            skills = get_skill_list(candidate)

            skills_html = display_skills(skills)

            st.markdown(
                f"""
                <div style="
                    background:white;
                    border:1px solid #d9dee8;
                    padding:15px;
                    border-radius:8px;
                    margin-bottom:8px;
                ">

                    <div style="
                        display:grid;
                        grid-template-columns:1.2fr 1.6fr 1fr 3fr 0.8fr;
                        gap:15px;
                        align-items:center;
                    ">

                        <div>
                            <small>Candidate Name</small><br>
                            <b>{name}</b>
                        </div>

                        <div>
                            <small>Email</small><br>
                            {email}
                        </div>

                        <div>
                            <small>Experience</small><br>
                            {experience}
                        </div>

                        <div>
                            <small>Key Skills</small><br>
                            {skills_html}
                        </div>

                        <div>
                            <span class="status-pill">
                                Processed
                            </span>
                        </div>

                    </div>

                </div>
                """,
                unsafe_allow_html=True
            )

    else:

        st.info(
            "No candidates processed yet."
        )


# ============================================================
# CANDIDATES PAGE
# ============================================================

elif page == "👥 Candidates":

    st.markdown(
        '<div class="main-title">Candidate Directory</div>',
        unsafe_allow_html=True
    )

    st.markdown(
        '<div class="subtitle">View all processed candidates</div>',
        unsafe_allow_html=True
    )

    candidates = get_all_candidates()

    if not candidates:

        st.info(
            "No candidates found. Upload a resume first."
        )

    else:

        for candidate in candidates:

            name = candidate.get("name") or "Not found"

            with st.expander(
                f"👤 {name}"
            ):

                col1, col2 = st.columns(2)

                with col1:

                    st.write(
                        f"**Email:** {candidate.get('email') or 'Not found'}"
                    )

                    st.write(
                        f"**Phone:** {candidate.get('phone') or 'Not found'}"
                    )

                    st.write(
                        f"**Location:** {candidate.get('location') or 'Not found'}"
                    )

                    st.write(
                        f"**Education:** {candidate.get('education') or 'Not found'}"
                    )

                with col2:

                    st.write(
                        f"**Experience:** {candidate.get('experience') or 'Not found'}"
                    )

                    st.write(
                        f"**Certifications:** {candidate.get('certifications') or 'Not found'}"
                    )

                    st.write(
                        f"**Projects:** {candidate.get('projects') or 'Not found'}"
                    )

                st.write("**Skills:**")

                skills = get_skill_list(candidate)

                st.markdown(
                    display_skills(skills),
                    unsafe_allow_html=True
                )

                st.write("**Summary:**")

                st.write(
                    candidate.get("summary")
                    or "Not found"
                )


# ============================================================
# SKILLS ANALYTICS PAGE
# ============================================================

elif page == "📊 Skills Analytics":

    st.markdown(
        '<div class="main-title">Skills Analytics</div>',
        unsafe_allow_html=True
    )

    st.markdown(
        '<div class="subtitle">Analyze skills extracted from all candidate resumes</div>',
        unsafe_allow_html=True
    )

    candidates = get_all_candidates()

    all_skills = get_all_skills(candidates)

    skill_counts = normalize_skills(all_skills)

    unique_skills = len(skill_counts)

    total_occurrences = sum(
        skill_counts.values()
    )

    # ========================================================
    # TOP METRICS
    # ========================================================

    metric1, metric2, metric3 = st.columns(3)

    # TOP SKILL
    if skill_counts:

        top_skill, top_count = (
            skill_counts.most_common(1)[0]
        )

    else:

        top_skill = "—"
        top_count = 0

    with metric1:

        st.markdown(
            f"""
            <div class="metric-card">
                <div class="metric-label">
                    Total Unique Skills
                </div>

                <div class="metric-value">
                    {unique_skills}
                </div>
            </div>
            """,
            unsafe_allow_html=True
        )

    with metric2:

        st.markdown(
            f"""
            <div class="metric-card">
                <div class="metric-label">
                    Top Skill
                </div>

                <div class="metric-value"
                     style="font-size:1.8rem">
                    {top_skill}
                </div>
            </div>
            """,
            unsafe_allow_html=True
        )

    with metric3:

        st.markdown(
            f"""
            <div class="metric-card">
                <div class="metric-label">
                    Total Occurrences
                </div>

                <div class="metric-value">
                    {total_occurrences}
                </div>
            </div>
            """,
            unsafe_allow_html=True
        )

    st.write("")

    # ========================================================
    # CHARTS
    # ========================================================

    chart_left, chart_right = st.columns(2)

    # ========================================================
    # TOP 20 SKILLS
    # ========================================================

    with chart_left:

        st.markdown(
            """
            <div class="card-title">
                Top 20 Skills
            </div>
            """,
            unsafe_allow_html=True
        )

        top20 = skill_counts.most_common(20)

        if top20:

            max_count = max(
                count for skill, count in top20
            )

            for skill, count in top20:

                width = (
                    count / max_count
                ) * 100

                st.markdown(
                    f"""
                    <div class="bar-container">

                        <div class="bar-label">
                            <span>{skill}</span>
                            <span>{count}</span>
                        </div>

                        <div class="bar-background">

                            <div class="bar-fill"
                                 style="width:{width}%">
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


    # ========================================================
    # SKILL DISTRIBUTION TOP 5
    # ========================================================

    with chart_right:

        st.markdown(
            """
            <div class="card-title">
                Skill Distribution (Top 5)
            </div>
            """,
            unsafe_allow_html=True
        )

        top5 = skill_counts.most_common(5)

        if top5:

            total_top5 = sum(
                count
                for skill, count in top5
            )

            # Generate percentages
            percentages = []

            for skill, count in top5:

                percentage = (
                    count / total_top5
                ) * 100

                percentages.append(
                    percentage
                )

            # Create CSS conic gradient
            colors = [
                "#6366f1",
                "#8b5cf6",
                "#a855f7",
                "#c084fc",
                "#e879f9"
            ]

            gradient_parts = []

            current = 0

            for i, percentage in enumerate(
                percentages
            ):

                start = current

                end = current + percentage

                gradient_parts.append(
                    f"{colors[i]} {start}% {end}%"
                )

                current = end

            gradient = ", ".join(
                gradient_parts
            )

            legend_html = ""

            for i, (
                skill,
                count
            ) in enumerate(top5):

                percentage = (
                    count / total_top5
                ) * 100

                legend_html += f"""
                <div class="legend-item">

                    <div class="legend-box"
                         style="background:{colors[i]}">
                    </div>

                    <span>
                        {skill} — {percentage:.1f}%
                    </span>

                </div>
                """

            st.markdown(
                f"""
                <div class="pie-wrapper">

                    <div
                        class="pie-chart"
                        style="
                            background:conic-gradient(
                                {gradient}
                            );
                        ">
                    </div>

                    <div>
                        {legend_html}
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
# FOOTER
# ============================================================

st.markdown("---")

st.markdown(
    """
    <div style="
        text-align:center;
        color:#94a3b8;
        font-size:0.8rem;
    ">
        Recruitment Copilot • Resume Parsing & Candidate Profiling
    </div>
    """,
    unsafe_allow_html=True
)