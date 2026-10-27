"""
analytics_db.py
Read-only queries that feed the Dashboard and the Skill Gap Analysis page.
Kept separate from db.py so the core data layer stays untouched.
"""

import json

from db import get_connection


def get_application_counts_per_job():
    """One row per job posting with how many candidates applied (0 included)."""
    conn = get_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("""
        SELECT j.id, j.title, COUNT(a.id) AS applications
        FROM job_postings j
        LEFT JOIN job_applications a ON a.job_id = j.id
        GROUP BY j.id, j.title
        ORDER BY applications DESC, j.title
    """)
    rows = cursor.fetchall()
    cursor.close()
    conn.close()
    return rows


def get_all_applications_detailed():
    """Every application joined with the job's requirements and the
    applicant's parsed-resume skills, so required-vs-candidate skills can be
    compared without extra queries."""
    conn = get_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("""
        SELECT a.id AS application_id, a.applied_at,
               j.id AS job_id, j.title AS job_title,
               j.required_skills, j.experience_required,
               c.id AS candidate_id, c.name, c.email, c.skills, c.experience
        FROM job_applications a
        JOIN job_postings j ON j.id = a.job_id
        JOIN candidates c ON c.id = a.candidate_id
        ORDER BY a.applied_at DESC
    """)
    rows = cursor.fetchall()
    cursor.close()
    conn.close()
    for row in rows:
        row["required_skills"] = json.loads(row["required_skills"] or "[]")
    return rows


def get_pipeline_counts():
    """Distinct candidates reaching each stage of the real workflow:
    sign-up -> resume uploaded -> applied -> interview sent -> completed."""
    conn = get_connection()
    cursor = conn.cursor()

    def one(sql):
        cursor.execute(sql)
        return cursor.fetchone()[0]

    counts = {
        "signed_up": one("SELECT COUNT(*) FROM candidate_accounts"),
        "resume_uploaded": one(
            "SELECT COUNT(DISTINCT candidate_account_id) FROM candidates "
            "WHERE candidate_account_id IS NOT NULL"
        ),
        "applied": one("SELECT COUNT(DISTINCT candidate_account_id) FROM job_applications"),
        "interview_sent": one(
            "SELECT COUNT(DISTINCT candidate_account_id) FROM interview_sessions "
            "WHERE status IN ('ready', 'completed')"
        ),
        "interview_completed": one(
            "SELECT COUNT(DISTINCT candidate_account_id) FROM interview_sessions "
            "WHERE status = 'completed'"
        ),
    }
    cursor.close()
    conn.close()
    return counts


def get_recent_sessions(limit=8):
    """Latest interview sessions (any recruiter) with the candidate's name."""
    conn = get_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("""
        SELECT s.job_role, s.difficulty, s.status, s.created_at, c.name AS candidate_name
        FROM interview_sessions s
        JOIN candidate_accounts c ON c.id = s.candidate_account_id
        ORDER BY s.created_at DESC
        LIMIT %s
    """, (limit,))
    rows = cursor.fetchall()
    cursor.close()
    conn.close()
    return rows