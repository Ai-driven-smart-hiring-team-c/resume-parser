"""
skill_gap_page.py
Skill Gap Analysis: pick a job, then see for every applicant (or every
candidate) which required skills they have, which are missing, and how their
experience compares with what the job asks for.

build_overview_blocks() / build_detail_html() are pure (data in, HTML out) so
the layout can be previewed without a database.
"""

from collections import Counter

from skill_gap_utils import parse_skill_list, compute_gap, verdict
from ui_theme import (
    render, esc, page_header_html, ledger_html, panel_html, empty_html, insights_html,
    bars_html, strip_html, strip_key_html, chips_html, pill_html, subhead_html,
    candidate_rows_html,
)

VERDICT_TONE = {"Strong Match": ("Strong match", "ok"), "Possible Match": ("Possible match", "warn"),
                "Weak Match": ("Weak match", "bad")}


def _unique_labels(people):
    """Names can repeat, so add the id only where needed to keep dropdown
    entries distinct."""
    counts = Counter(p["name"] for p in people)
    return [f"{p['name']} (#{p['candidate_id']})" if counts[p["name"]] > 1 else p["name"] for p in people]


def build_overview_blocks(job, required, required_years, rows):
    """rows: dicts {label, person, gap, years}. Returns HTML blocks, top to bottom."""
    n = len(rows)
    avg = sum(r["gap"]["coverage"] for r in rows) / n
    qualified = sum(1 for r in rows if r["gap"]["coverage"] >= 100)
    missed = Counter()
    for r in rows:
        missed.update(r["gap"]["missing"])
    top_missed = missed.most_common(1)

    blocks = []

    # job requirements
    experience = f"{required_years:g} years of experience" if required_years else "No minimum experience"
    education = job.get("education_required") or "No education requirement"
    blocks.append(panel_html(
        job["title"], f"{experience}. {education}.",
        subhead_html(f"Required skills ({len(required)})") + chips_html(required, "neutral")))

    # summary ledger
    blocks.append(ledger_html([
        {"value": n, "label": "Candidates analysed"},
        {"value": f"{avg:.0f}%", "label": "Average skill match",
         "hint": "Share of required skills covered", "tone": ""},
        {"value": qualified, "label": "Cover every required skill",
         "hint": "Ready to move forward" if qualified else "Nobody covers them all yet",
         "tone": "ok" if qualified else "warn"},
        {"value": top_missed[0][0] if top_missed else "None", "label": "Most-missed skill", "text": True,
         "hint": f"{top_missed[0][1]} of {n} candidates lack it" if top_missed else "No gaps found",
         "tone": "bad" if top_missed else "ok"},
    ]))

    # ranking next to availability
    ordered = sorted(rows, key=lambda r: -r["gap"]["coverage"])
    ranking = panel_html(
        "Candidates ranked by skill coverage",
        "Each segment is one required skill.",
        strip_key_html().replace('class="key"', 'class="key" style="margin:0 0 6px"') +
        candidate_rows_html([
            {"name": r["label"], "email": r["person"].get("email") or "", "required": required,
             "matched": r["gap"]["matched"], "coverage": r["gap"]["coverage"],
             "missing_count": len(r["gap"]["missing"])}
            for r in ordered]))

    availability_rows = []
    for skill in required:
        have = sum(1 for r in rows if skill in r["gap"]["matched"])
        share = have / n
        tone = "teal" if share >= 0.66 else ("amber" if share >= 0.33 else "coral")
        availability_rows.append((skill, have, f"of {n}", tone))
    availability = panel_html(
        "Which skills are hard to find", "How many of these candidates have each required skill.",
        bars_html(sorted(availability_rows, key=lambda r: r[1]), max_value=n))
    blocks.append(f'<div class="grid g32">{ranking}{availability}</div>')
    return blocks


def _experience_sentence(years, required_years):
    if not required_years:
        return f"Experience: {years:g} years. The job sets no minimum."
    if years > required_years:
        return f"Experience: {years:g} years, {years - required_years:g} more than the {required_years:g} required."
    if years == required_years:
        return f"Experience: {years:g} years, exactly what the job requires."
    return f"Experience: {years:g} years, {required_years - years:g} short of the {required_years:g} required."


def build_detail_html(row, required, required_years):
    person, gap = row["person"], row["gap"]
    label, tone = VERDICT_TONE.get(verdict(gap["coverage"])[0], ("Match", "neutral"))
    covered = f'{len(gap["matched"])} of {len(required)} required skills'

    notes = [("ok" if (not required_years or row["years"] >= required_years) else "warn",
              esc(_experience_sentence(row["years"], required_years)))]
    if gap["missing"]:
        notes.append(("bad", "To close the gap: <b>" + "</b>, <b>".join(esc(s) for s in gap["missing"]) + "</b>."))
    else:
        notes.append(("ok", "Covers every required skill. A strong candidate to move forward."))

    head = (
        f'<div class="detail-head"><div><div class="detail-name">{esc(person["name"])}</div>'
        f'<div class="muted">{esc(person.get("email") or "")}</div>'
        f'<div style="margin-top:10px">{pill_html(label, tone)}</div></div>'
        f'<div class="detail-pct">{gap["coverage"]:.0f}%<small>{esc(covered)}</small></div></div>'
    )
    trio = (
        '<div class="trio">'
        f'<div>{subhead_html("Has")}{chips_html(gap["matched"], "ok")}</div>'
        f'<div>{subhead_html("Missing")}{chips_html(gap["missing"], "bad")}</div>'
        f'<div>{subhead_html("Also has")}{chips_html(gap["extra"], "neutral")}</div></div>'
    )
    body = head + strip_html(required, gap["matched"], large=True) + strip_key_html() + trio + \
        '<div style="margin-top:22px">' + insights_html(notes) + "</div>"
    return f'<div class="panel">{body}</div>'


def render_skill_gap_page():
    import pandas as pd
    import streamlit as st
    from db import get_all_jobs, get_all_candidates, get_applications_for_job
    from profile_utils import extract_years

    render(page_header_html(
        "Skill gap analysis",
        "Pick a job to see which required skills each candidate has and which they are missing."))

    jobs = get_all_jobs()
    if not jobs:
        render(empty_html("No job postings yet", "An admin adds one under Job Matching, then it shows up here."))
        return

    job_labels = {f"{j['title']} (#{j['id']})": j for j in jobs}
    col_job, col_scope = st.columns([2, 1])
    with col_job:
        picked_job = st.selectbox("Job posting", list(job_labels.keys()))
    with col_scope:
        scope = st.radio("Analyse", ["Applicants only", "All candidates"], horizontal=True)

    job = job_labels[picked_job]
    required = parse_skill_list(job.get("required_skills"))
    required_years = float(job.get("experience_required") or 0)

    if not required:
        render(panel_html(job["title"], "", empty_html(
            "No skills found in this job description",
            "Edit the posting so it names specific skills such as Python, SQL or AWS.")))
        return

    if scope == "Applicants only":
        people = get_applications_for_job(job["id"])
        if not people:
            render(panel_html(job["title"], "", empty_html(
                "Nobody has applied to this job yet",
                "Switch to All candidates to preview how the existing pool fits.")))
            return
    else:
        people = [
            {"candidate_id": c["id"], "name": c.get("name") or "Not found", "email": c.get("email") or "",
             "skills": c.get("skills"), "experience": c.get("experience"),
             "resume_file": c.get("resume_file"), "resume_file_name": c.get("resume_file_name"),
             "applied_at": None}
            for c in get_all_candidates()
        ]
        if not people:
            render(empty_html("No candidates yet", "Upload a resume or ask candidates to sign up."))
            return

    rows = []
    for label, p in zip(_unique_labels(people), people):
        rows.append({"label": label, "person": p,
                     "gap": compute_gap(required, parse_skill_list(p.get("skills"))),
                     "years": extract_years(p.get("experience"))})

    for block in build_overview_blocks(job, required, required_years, rows):
        render(block)

    # one candidate in detail
    by_label = {r["label"]: r for r in rows}
    picked = st.selectbox("Look at one candidate",
                          sorted(by_label, key=lambda l: -by_label[l]["gap"]["coverage"]))
    chosen = by_label[picked]
    render(build_detail_html(chosen, required, required_years))

    person = chosen["person"]
    if person.get("resume_file"):
        st.download_button("Download resume", data=person["resume_file"],
                           file_name=person.get("resume_file_name") or "resume",
                           key=f"gap_dl_{job['id']}_{person['candidate_id']}")

    with st.expander("Full comparison table"):
        table = pd.DataFrame([{
            "Candidate": r["label"],
            "Skill match (%)": r["gap"]["coverage"],
            "Skills covered": f"{len(r['gap']['matched'])}/{len(required)}",
            "Missing skills": ", ".join(r["gap"]["missing"]) or "None",
            "Experience (yrs)": r["years"],
            "Required (yrs)": required_years,
        } for r in rows]).sort_values("Skill match (%)", ascending=False)
        st.dataframe(table, use_container_width=True, hide_index=True)