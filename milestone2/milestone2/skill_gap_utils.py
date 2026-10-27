"""
skill_gap_utils.py
Shared helpers for comparing a job's required skills against a
candidate's resume skills. Used by both the Dashboard and the Skill Gap
Analysis page so the numbers always agree.
"""

import json
from typing import List, Dict, Tuple


def parse_skill_list(value) -> List[str]:
    """Candidate skills are stored as a comma-separated string ('Python,
    SQL'), or the literal 'Not found' when the parser found nothing. Job
    skills are stored as a JSON list. Handle all of these and return a clean
    list of skill names."""
    if not value:
        return []
    if isinstance(value, list):
        items = value
    else:
        text = str(value).strip()
        if text.lower() == "not found":
            return []
        if text.startswith("["):
            try:
                items = json.loads(text)
            except ValueError:
                items = text.strip("[]").split(",")
        else:
            items = text.split(",")
    cleaned = []
    for item in items:
        name = str(item).strip().strip('"').strip("'")
        if name and name.lower() != "not found":
            cleaned.append(name)
    return cleaned


def compute_gap(required: List[str], candidate_skills: List[str]) -> Dict:
    """Case-insensitive comparison.

    Returns:
        matched   -- required skills the candidate has
        missing   -- required skills the candidate lacks
        extra     -- skills the candidate has beyond what the job asks for
        coverage  -- % of required skills covered (0-100)
    """
    candidate_lookup = {s.lower() for s in candidate_skills}
    required_lookup = {s.lower() for s in required}

    matched = [s for s in required if s.lower() in candidate_lookup]
    missing = [s for s in required if s.lower() not in candidate_lookup]
    extra = [s for s in candidate_skills if s.lower() not in required_lookup]
    coverage = round(100 * len(matched) / len(required), 1) if required else 0.0

    return {
        "matched": matched,
        "missing": missing,
        "extra": extra,
        "coverage": coverage,
    }


def verdict(coverage: float) -> Tuple[str, str, str]:
    """(label, text_color, background_color) -- same 85 / 60 thresholds the
    Job Matching page uses for 'Strong' / 'Possible' / 'Weak'."""
    if coverage >= 85:
        return "Strong Match", "#15803d", "#dcfce7"
    if coverage >= 60:
        return "Possible Match", "#b45309", "#fef3c7"
    return "Weak Match", "#b91c1c", "#fee2e2"


def badges_html(skills: List[str], color="#eef2ff", text_color="#3730a3") -> str:
    if not skills:
        return "<span style='color:#667085;'>None</span>"
    return "".join(
        f"<span style='display:inline-block;background:{color};color:{text_color};"
        f"border-radius:15px;padding:4px 10px;margin:3px;font-size:12px;'>{s}</span>"
        for s in skills
    )


# ============================================================
# Chart + card helpers (streamlit/altair imported lazily so the pure
# functions above stay importable and testable without them)
# ============================================================

BLUE = "#2563eb"
PURPLE = "#7c3aed"
GREEN = "#10b981"
RED = "#ef4444"
AMBER = "#f59e0b"


def stat_card(label: str, value) -> str:
    """Same markup as the app's other stat cards (uses app.py's CSS)."""
    return (
        f'<div class="stat-card"><div class="stat-label">{label}</div>'
        f'<div class="stat-value">{value}</div></div>'
    )


def hbar_chart(df, label_col, value_col, color=BLUE, order=None, max_value=None):
    """Horizontal bar chart. order=None sorts by value (largest on top);
    pass an explicit list to keep a fixed order (e.g. pipeline stages)."""
    import altair as alt
    import streamlit as st

    scale = alt.Scale(domain=[0, max_value]) if max_value else alt.Undefined
    chart = (
        alt.Chart(df)
        .mark_bar(color=color, cornerRadiusEnd=4)
        .encode(
            x=alt.X(f"{value_col}:Q", title=None, scale=scale, axis=alt.Axis(tickMinStep=1)),
            y=alt.Y(f"{label_col}:N", sort=order if order else "-x", title=None),
            tooltip=[label_col, value_col],
        )
        .properties(height=max(140, 34 * len(df) + 20))
    )
    st.altair_chart(chart, use_container_width=True)


def vbar_chart(df, label_col, value_col, order, color=BLUE):
    """Vertical bar chart with a fixed category order."""
    import altair as alt
    import streamlit as st

    chart = (
        alt.Chart(df)
        .mark_bar(color=color, cornerRadiusTopLeft=4, cornerRadiusTopRight=4)
        .encode(
            x=alt.X(f"{label_col}:N", sort=order, title=None, axis=alt.Axis(labelAngle=0)),
            y=alt.Y(f"{value_col}:Q", title=None, axis=alt.Axis(tickMinStep=1)),
            tooltip=[label_col, value_col],
        )
        .properties(height=260)
    )
    st.altair_chart(chart, use_container_width=True)


def donut_chart(df, label_col, value_col, domain, colors):
    import altair as alt
    import streamlit as st

    chart = (
        alt.Chart(df)
        .mark_arc(innerRadius=60)
        .encode(
            theta=alt.Theta(f"{value_col}:Q"),
            color=alt.Color(
                f"{label_col}:N",
                scale=alt.Scale(domain=domain, range=colors),
                legend=alt.Legend(orient="bottom", title=None),
            ),
            tooltip=[label_col, value_col],
        )
        .properties(height=290)
    )
    st.altair_chart(chart, use_container_width=True)