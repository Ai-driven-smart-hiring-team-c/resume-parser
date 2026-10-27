"""
dashboard_page.py
Hiring overview built from the app's real data.

build_dashboard_blocks() is a pure function (data in, HTML strings out) so the
layout can be previewed without a database. render_dashboard_page() loads the
data and renders those blocks.
"""

from collections import Counter

from skill_gap_utils import parse_skill_list, compute_gap
from ui_theme import (
    render, esc, page_header_html, ledger_html, panel_html, split_html, subhead_html,
    empty_html, insights_html, bars_html, columns_html, stacked_html, strip_html,
    chips_html, pill_html, table_html, name_cell_html,
)

MATCH_BINS = [
    ("90-100", 90, "teal"),
    ("80-89", 80, "teal"),
    ("70-79", 70, "amber"),
    ("60-69", 60, "amber"),
    ("Below 60", 0, "coral"),
]
STATUS_LABEL = {"pending_review": ("Pending review", "warn"), "ready": ("Sent", "neutral"), "completed": ("Completed", "ok")}


def _plural(n: int, word: str) -> str:
    return f"{n} {word}" if n == 1 else f"{n} {word}s"


def _bin_for(coverage: float) -> str:
    for label, floor, _ in MATCH_BINS:
        if coverage >= floor:
            return label
    return MATCH_BINS[-1][0]


def _missing_chips(missing, limit=4) -> str:
    if not missing:
        return '<span class="muted">None</span>'
    shown = chips_html(missing[:limit], "bad")
    extra = len(missing) - limit
    return shown + (f'<span class="muted">+{extra} more</span>' if extra > 0 else "")


def build_dashboard_blocks(candidates, jobs, applications, pipeline, interview_counts,
                           hiring_scores, per_job, sessions):
    """Returns a list of HTML strings, rendered top to bottom."""
    # compare every applicant's resume skills with the job they applied to
    rows = []
    for a in applications:
        gap = compute_gap(a["required_skills"], parse_skill_list(a["skills"]))
        rows.append({**a, **gap})

    n_apps = len(rows)
    avg_match = sum(r["coverage"] for r in rows) / n_apps if n_apps else None
    strong = sum(1 for r in rows if r["coverage"] >= 85)
    pending = interview_counts.get("pending_review", 0)
    sent = interview_counts.get("ready", 0)
    completed = interview_counts.get("completed", 0)
    jobs_without_applicants = sum(1 for j in per_job if j["applications"] == 0)

    blocks = []

    # ---- header -------------------------------------------------------
    if n_apps:
        sentence = (f"{_plural(n_apps, 'application')} across {_plural(len(jobs), 'job')}, "
                    f"from a talent pool of {_plural(len(candidates), 'candidate')}.")
    else:
        sentence = (f"{_plural(len(candidates), 'candidate')} in the talent pool and "
                    f"{_plural(len(jobs), 'open job')}. Applications show up here as candidates apply.")
    blocks.append(page_header_html("Hiring overview", sentence))

    # ---- KPI ledger ---------------------------------------------------
    blocks.append(ledger_html([
        {"value": len(candidates), "label": "Candidates in the pool",
         "hint": f"{pipeline['signed_up']} signed up on the portal"},
        {"value": len(jobs), "label": "Open jobs",
         "hint": (f"{_plural(jobs_without_applicants, 'job')} with no applicants yet"
                  if jobs_without_applicants else "Every job has applicants"),
         "tone": "warn" if jobs_without_applicants else "ok"},
        {"value": n_apps, "label": "Applications received",
         "hint": f"From {_plural(pipeline['applied'], 'candidate')}"},
        {"value": completed, "label": "Interviews completed",
         "hint": f"{pending} to review, {sent} sent", "tone": "warn" if pending else ""},
        {"value": f"{avg_match:.0f}%" if avg_match is not None else "n/a", "label": "Average skill match",
         "hint": f"{_plural(strong, 'strong match')} at 85% or more" if n_apps else "Needs applications",
         "tone": "ok" if strong else ""},
    ]))

    # ---- what needs attention ------------------------------------------
    missing_counter = Counter()
    for r in rows:
        missing_counter.update(r["missing"])
    notes = []
    if missing_counter:
        skill, count = missing_counter.most_common(1)[0]
        notes.append(("bad", f"<b>{esc(skill)}</b> is the skill applicants lack most: "
                             f"{count} of {n_apps} applications are missing it."))
    if rows:
        best = max(rows, key=lambda r: r["coverage"])
        if best["coverage"] > 0:
            notes.append(("ok", f"<b>{esc(best['name'])}</b> is the strongest fit so far, covering "
                                f"{best['coverage']:.0f}% of the skills required for {esc(best['job_title'])}."))
    if pending:
        notes.append(("warn", f"<b>{_plural(pending, 'interview')}</b> waiting for your review before "
                              f"they can be sent to candidates."))
    if sent:
        notes.append(("", f"{_plural(sent, 'interview')} sent and waiting for the candidate to answer."))
    body = insights_html(notes) if notes else empty_html(
        "Nothing to flag yet", "Insights appear once candidates apply to jobs.")
    blocks.append(panel_html("What needs attention", "Worked out from your current data", body))

    # ---- pipeline + interview status ------------------------------------
    stages = [
        ("Signed up", pipeline["signed_up"]),
        ("Uploaded a resume", pipeline["resume_uploaded"]),
        ("Applied to a job", pipeline["applied"]),
        ("Interview sent", pipeline["interview_sent"]),
        ("Interview completed", pipeline["interview_completed"]),
    ]
    stage_rows = []
    for i, (label, value) in enumerate(stages):
        extra = ""
        if i > 0 and stages[i - 1][1] > 0:
            extra = f"{value / stages[i - 1][1] * 100:.0f}%"
        stage_rows.append((label, value, extra, "teal" if i == len(stages) - 1 else ""))
    pipeline_panel = panel_html(
        "Candidate pipeline", "Candidates who reached each stage. The percentage is the share of the stage before.",
        bars_html(stage_rows) if pipeline["signed_up"] else empty_html(
            "No candidates yet", "Candidates appear here after they sign up on the portal."))

    if pending + sent + completed:
        status_body = stacked_html([
            ("Pending review", pending, "var(--amber)"),
            ("Sent to candidate", sent, "var(--cobalt)"),
            ("Completed", completed, "var(--teal)"),
        ])
    else:
        status_body = empty_html("No interviews yet", "Create one from Interview Assistant.")
    status_panel = panel_html("Interview status", "Where every interview session stands", status_body)
    blocks.append(f'<div class="grid g32">{pipeline_panel}{status_panel}</div>')

    # ---- skills: gaps next to talent pool ----------------------------------
    pool = Counter()
    for c in candidates:
        pool.update(parse_skill_list(c.get("skills")))
    gap_side = subhead_html("Required skills applicants are missing") + (
        bars_html(missing_counter.most_common(8), tone="coral") if missing_counter
        else empty_html("No gaps to show", "Gaps appear once candidates apply to jobs."))
    pool_side = subhead_html("Most common skills in the talent pool") + (
        bars_html(pool.most_common(8)) if pool else empty_html("No resumes parsed yet", "Upload a resume to start."))
    blocks.append(panel_html("Skills", "What jobs ask for compared with what candidates bring",
                             split_html(gap_side, pool_side)))

    # ---- applications: match spread + per job --------------------------------
    counts = Counter(_bin_for(r["coverage"]) for r in rows)
    fit_side = subhead_html("How well applicants fit the job they applied to") + (
        columns_html([(label, counts.get(label, 0), tone) for label, _, tone in MATCH_BINS]) if rows
        else empty_html("No applications yet", "The spread appears after the first application."))
    job_side = subhead_html("Applications per job") + (
        bars_html([(j["title"], j["applications"]) for j in per_job[:8]], tone="") if per_job
        else empty_html("No job postings yet", "An admin adds them under Job Matching."))
    blocks.append(panel_html("Applications", "Skill match is the share of a job's required skills the applicant has",
                             split_html(fit_side, job_side)))

    # ---- rankings ------------------------------------------------------------
    best_per_candidate = {}
    for r in rows:
        cur = best_per_candidate.get(r["candidate_id"])
        if cur is None or r["coverage"] > cur["coverage"]:
            best_per_candidate[r["candidate_id"]] = r
    ranked = sorted(best_per_candidate.values(), key=lambda r: -r["coverage"])[:10]
    if ranked:
        trs = []
        for r in ranked:
            score = hiring_scores.get(r["candidate_id"])
            score_cell = (f'<span class="figure">{float(score):.0f}</span>' if score is not None
                          else '<span class="muted">Not run</span>')
            trs.append([
                name_cell_html(r["name"], r["email"]),
                esc(r["job_title"]),
                f'<div class="cov">{strip_html(r["required_skills"], r["matched"])}'
                f'<span class="figure">{r["coverage"]:.0f}%</span></div>',
                score_cell,
                _missing_chips(r["missing"]),
            ])
        rank_body = table_html(["Candidate", "Best fit for", "Skill coverage", "Hiring score", "Missing skills"], trs)
    else:
        rank_body = empty_html("Rankings appear after the first application",
                               "Each candidate is ranked by how many of a job's required skills they have.")
    blocks.append(panel_html(
        "Candidate rankings", "Each segment is one required skill: teal means the candidate has it, coral means it is missing.",
        rank_body))

    # ---- recent activity ------------------------------------------------------
    if rows:
        left = table_html(["Candidate", "Applied for", "Match", "When"], [
            [name_cell_html(r["name"]), esc(r["job_title"]),
             f'<span class="figure">{r["coverage"]:.0f}%</span>', esc(str(r["applied_at"])[:16])]
            for r in rows[:6]])
    else:
        left = empty_html("No applications yet", "")
    if sessions:
        right = table_html(["Candidate", "Role", "Status", "Created"], [
            [name_cell_html(s["candidate_name"], s["difficulty"]), esc(s["job_role"]),
             pill_html(*STATUS_LABEL.get(s["status"], (s["status"], "neutral"))), esc(str(s["created_at"])[:16])]
            for s in sessions[:6]])
    else:
        right = empty_html("No interviews yet", "")
    blocks.append(panel_html("Recent activity", "",
                             split_html(subhead_html("Latest applications") + left,
                                        subhead_html("Latest interviews") + right)))
    return blocks


def render_dashboard_page():
    # imported here so build_dashboard_blocks stays importable without a database
    from db import get_all_candidates, get_all_jobs, get_top_candidates_overall
    from interview_db import get_interview_status_counts
    from analytics_db import (
        get_application_counts_per_job, get_all_applications_detailed,
        get_pipeline_counts, get_recent_sessions,
    )

    blocks = build_dashboard_blocks(
        candidates=get_all_candidates(),
        jobs=get_all_jobs(),
        applications=get_all_applications_detailed(),
        pipeline=get_pipeline_counts(),
        interview_counts=get_interview_status_counts(),
        hiring_scores={r["id"]: r["best_score"] for r in get_top_candidates_overall(limit=1000)},
        per_job=get_application_counts_per_job(),
        sessions=get_recent_sessions(limit=8),
    )
    for block in blocks:
        render(block)