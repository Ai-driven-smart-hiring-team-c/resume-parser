"""
db.py
Handles all database work for the Recruitment Copilot, using MySQL.

Connection settings come from settings.get_setting (environment variables, or
Streamlit secrets when deployed):
    DB_HOST      default localhost
    DB_PORT      default 3306
    DB_USER      default root
    DB_PASSWORD  required -- there is no hardcoded fallback
    DB_NAME      default recruitment_copilot

Locally:    setx DB_PASSWORD your_password        (Windows, then restart VS Code)
Deployed:   put the same names in the Streamlit "Secrets" box (see DEPLOY steps).
"""

import json
from datetime import datetime

import mysql.connector
from mysql.connector import errors as mysql_errors

from settings import get_setting

DB_HOST = get_setting("DB_HOST", "localhost")
DB_PORT = int(get_setting("DB_PORT", "3306") or 3306)
DB_USER = get_setting("DB_USER", "root")
DB_PASSWORD = get_setting("DB_PASSWORD")
DB_NAME = get_setting("DB_NAME", "recruitment_copilot")

if DB_PASSWORD is None:
    raise RuntimeError(
        "DB_PASSWORD is not set. Set it as an environment variable "
        "(Windows: setx DB_PASSWORD your_password, then restart VS Code) "
        "or add it to the Streamlit Secrets when deployed."
    )


def get_connection(with_database=True):
    return mysql.connector.connect(
        host=DB_HOST,
        port=DB_PORT,
        user=DB_USER,
        password=DB_PASSWORD,
        database=DB_NAME if with_database else None,
        connection_timeout=15,
    )


def init_db():
    # Managed hosts (Aiven etc.) create the database for you and may refuse
    # CREATE DATABASE; that is fine, the next connection tells us if it is missing.
    try:
        conn = get_connection(with_database=False)
        cursor = conn.cursor()
        cursor.execute(f"CREATE DATABASE IF NOT EXISTS `{DB_NAME}`")
        cursor.close()
        conn.close()
    except mysql_errors.Error:
        pass

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS candidates (
            id              INT AUTO_INCREMENT PRIMARY KEY,
            file_name       VARCHAR(255),
            name            VARCHAR(255),
            email           VARCHAR(255),
            phone           VARCHAR(50),
            location        VARCHAR(255),
            education       TEXT,
            experience      TEXT,
            skills          TEXT,
            certifications  TEXT,
            projects        TEXT,
            summary         TEXT,
            raw_text        LONGTEXT,
            uploaded_at     DATETIME
        )
    """)

    # -------------------- Milestone 2: job postings --------------------
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS job_postings (
            id                          INT AUTO_INCREMENT PRIMARY KEY,
            title                       VARCHAR(255),
            required_skills             TEXT,
            experience_required         FLOAT,
            education_required          VARCHAR(255),
            education_required_level    INT,
            raw_text                    LONGTEXT,
            created_at                  DATETIME
        )
    """)

    # -------------------- Milestone 2: stored match results -------------
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS match_results (
            id                  INT AUTO_INCREMENT PRIMARY KEY,
            job_id              INT,
            candidate_id        INT,
            hiring_score        FLOAT,
            skill_score         FLOAT,
            experience_score    FLOAT,
            education_score     FLOAT,
            matched_skills      TEXT,
            missing_skills      TEXT,
            created_at          DATETIME,
            FOREIGN KEY (job_id) REFERENCES job_postings(id) ON DELETE CASCADE,
            FOREIGN KEY (candidate_id) REFERENCES candidates(id) ON DELETE CASCADE
        )
    """)

    # -------------------- Recruiter / admin accounts (login) ------------
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS recruiters (
            id              INT AUTO_INCREMENT PRIMARY KEY,
            name            VARCHAR(255),
            email           VARCHAR(255) UNIQUE,
            password_salt   VARCHAR(64),
            password_hash   VARCHAR(128),
            role            VARCHAR(20) DEFAULT 'recruiter',
            created_at      DATETIME
        )
    """)

    # -------------------- Remember-me tokens (recruiters/admins) --------
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS remember_tokens (
            id              INT AUTO_INCREMENT PRIMARY KEY,
            recruiter_id    INT,
            token_hash      VARCHAR(128) UNIQUE,
            expires_at      DATETIME,
            created_at      DATETIME,
            FOREIGN KEY (recruiter_id) REFERENCES recruiters(id) ON DELETE CASCADE
        )
    """)

    # -------------------- Candidate accounts (interview takers) ---------
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS candidate_accounts (
            id              INT AUTO_INCREMENT PRIMARY KEY,
            name            VARCHAR(255),
            email           VARCHAR(255) UNIQUE,
            password_salt   VARCHAR(64),
            password_hash   VARCHAR(128),
            created_at      DATETIME
        )
    """)

    # -------------------- Remember-me tokens (candidates) ----------------
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS candidate_remember_tokens (
            id                  INT AUTO_INCREMENT PRIMARY KEY,
            candidate_account_id INT,
            token_hash          VARCHAR(128) UNIQUE,
            expires_at          DATETIME,
            created_at          DATETIME,
            FOREIGN KEY (candidate_account_id) REFERENCES candidate_accounts(id) ON DELETE CASCADE
        )
    """)

    conn.commit()

    # Backward-compatible: add `summary` column if an older DB predates it.
    cursor.execute("""
        SELECT COUNT(*) FROM information_schema.columns
        WHERE table_schema = %s AND table_name = 'candidates' AND column_name = 'summary'
    """, (DB_NAME,))
    if cursor.fetchone()[0] == 0:
        cursor.execute("ALTER TABLE candidates ADD COLUMN summary TEXT")
        conn.commit()

    # Backward-compatible: add `role` column if an older DB predates it.
    cursor.execute("""
        SELECT COUNT(*) FROM information_schema.columns
        WHERE table_schema = %s AND table_name = 'recruiters' AND column_name = 'role'
    """, (DB_NAME,))
    if cursor.fetchone()[0] == 0:
        cursor.execute("ALTER TABLE recruiters ADD COLUMN role VARCHAR(20) DEFAULT 'recruiter'")
        conn.commit()

    # Backward-compatible: link resumes to the candidate_account that
    # uploaded them (self-service uploads via candidate_portal.py).
    cursor.execute("""
        SELECT COUNT(*) FROM information_schema.columns
        WHERE table_schema = %s AND table_name = 'candidates' AND column_name = 'candidate_account_id'
    """, (DB_NAME,))
    if cursor.fetchone()[0] == 0:
        cursor.execute("ALTER TABLE candidates ADD COLUMN candidate_account_id INT NULL")
        conn.commit()

    # Backward-compatible: store the original resume file so recruiters can
    # download it (not just the extracted text).
    cursor.execute("""
        SELECT COUNT(*) FROM information_schema.columns
        WHERE table_schema = %s AND table_name = 'candidates' AND column_name = 'resume_file'
    """, (DB_NAME,))
    if cursor.fetchone()[0] == 0:
        cursor.execute("ALTER TABLE candidates ADD COLUMN resume_file LONGBLOB NULL")
        cursor.execute("ALTER TABLE candidates ADD COLUMN resume_file_name VARCHAR(255) NULL")
        conn.commit()

    # -------------------- Job applications (candidate applies to a job) -
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS job_applications (
            id                  INT AUTO_INCREMENT PRIMARY KEY,
            job_id              INT,
            candidate_account_id INT,
            candidate_id        INT,
            applied_at          DATETIME,
            FOREIGN KEY (job_id) REFERENCES job_postings(id) ON DELETE CASCADE,
            FOREIGN KEY (candidate_account_id) REFERENCES candidate_accounts(id) ON DELETE CASCADE,
            FOREIGN KEY (candidate_id) REFERENCES candidates(id) ON DELETE CASCADE,
            UNIQUE KEY unique_application (job_id, candidate_account_id)
        )
    """)
    conn.commit()

    cursor.close()
    conn.close()


# ============================================================
# CANDIDATES (resume-parsed profiles -- unrelated to candidate logins)
# ============================================================

def insert_candidate(profile: dict):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO candidates
            (file_name, name, email, phone, location, education,
             experience, skills, certifications, projects, summary, raw_text,
             candidate_account_id, resume_file, resume_file_name, uploaded_at)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
    """, (
        profile.get("file_name"),
        profile.get("name"),
        profile.get("email"),
        profile.get("phone"),
        profile.get("location"),
        profile.get("education"),
        profile.get("experience"),
        profile.get("skills"),
        profile.get("certifications"),
        profile.get("projects"),
        profile.get("summary"),
        profile.get("raw_text"),
        profile.get("candidate_account_id"),
        profile.get("resume_file"),
        profile.get("resume_file_name"),
        datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    ))
    conn.commit()
    candidate_id = cursor.lastrowid
    cursor.close()
    conn.close()
    return candidate_id


def delete_candidate(candidate_id: int):
    """Admin-only: remove a candidate's resume/profile entry entirely.
    Cascades to match_results and job_applications rows referencing it."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM candidates WHERE id = %s", (candidate_id,))
    conn.commit()
    deleted = cursor.rowcount > 0
    cursor.close()
    conn.close()
    return deleted


def get_resume_for_candidate_account(candidate_account_id: int):
    """Most recent parsed resume uploaded by this candidate account, if any."""
    conn = get_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("""
        SELECT * FROM candidates WHERE candidate_account_id = %s
        ORDER BY uploaded_at DESC LIMIT 1
    """, (candidate_account_id,))
    row = cursor.fetchone()
    cursor.close()
    conn.close()
    return row


# ============================================================
# JOB APPLICATIONS (candidate applies to a job posting)
# ============================================================

def apply_to_job(job_id: int, candidate_account_id: int, candidate_id: int):
    """Returns True on success, False if this candidate already applied to
    this job (relies on the UNIQUE constraint on job_id+candidate_account_id)."""
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("""
            INSERT INTO job_applications (job_id, candidate_account_id, candidate_id, applied_at)
            VALUES (%s, %s, %s, %s)
        """, (job_id, candidate_account_id, candidate_id, datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
        conn.commit()
        return True
    except mysql_errors.IntegrityError:
        return False
    finally:
        cursor.close()
        conn.close()


def has_applied(job_id: int, candidate_account_id: int) -> bool:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT COUNT(*) FROM job_applications WHERE job_id = %s AND candidate_account_id = %s",
        (job_id, candidate_account_id),
    )
    count = cursor.fetchone()[0]
    cursor.close()
    conn.close()
    return count > 0


def get_applications_for_job(job_id: int):
    """Recruiter-facing: every applicant for a job, with their resume info
    (including the raw file bytes + name, for a download button)."""
    conn = get_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("""
        SELECT a.id AS application_id, a.applied_at,
               c.id AS candidate_id, c.name, c.email, c.skills, c.experience,
               c.resume_file, c.resume_file_name
        FROM job_applications a
        JOIN candidates c ON c.id = a.candidate_id
        WHERE a.job_id = %s
        ORDER BY a.applied_at DESC
    """, (job_id,))
    rows = cursor.fetchall()
    cursor.close()
    conn.close()
    return rows


def get_application_count():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM job_applications")
    count = cursor.fetchone()[0]
    cursor.close()
    conn.close()
    return count


def get_top_candidates_overall(limit=10):
    """Best hiring score per candidate across every job they were matched
    against, for the dashboard's 'Candidate Rankings' table."""
    conn = get_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("""
        SELECT c.id, c.name, c.email, MAX(m.hiring_score) AS best_score
        FROM candidates c
        JOIN match_results m ON m.candidate_id = c.id
        GROUP BY c.id, c.name, c.email
        ORDER BY best_score DESC
        LIMIT %s
    """, (limit,))
    rows = cursor.fetchall()
    cursor.close()
    conn.close()
    return rows


def get_top_missing_skills(limit=10):
    """Aggregates the missing_skills JSON column across every stored match
    result to surface the most common skill gaps, for the dashboard."""
    from collections import Counter
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT missing_skills FROM match_results")
    rows = cursor.fetchall()
    cursor.close()
    conn.close()

    counter = Counter()
    for (missing_json,) in rows:
        try:
            skills = json.loads(missing_json or "[]")
        except (TypeError, ValueError):
            skills = []
        counter.update(skills)
    return counter.most_common(limit)


def get_applications_for_candidate(candidate_account_id: int):
    conn = get_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("""
        SELECT a.*, j.title AS job_title
        FROM job_applications a
        JOIN job_postings j ON j.id = a.job_id
        WHERE a.candidate_account_id = %s
        ORDER BY a.applied_at DESC
    """, (candidate_account_id,))
    rows = cursor.fetchall()
    cursor.close()
    conn.close()
    return rows


def get_all_candidates():
    conn = get_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM candidates ORDER BY uploaded_at DESC")
    rows = cursor.fetchall()
    cursor.close()
    conn.close()
    return rows


def get_candidate_count():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM candidates")
    count = cursor.fetchone()[0]
    cursor.close()
    conn.close()
    return count


# ============================================================
# JOB POSTINGS (Milestone 2)
# ============================================================

def insert_job(job: dict):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO job_postings
            (title, required_skills, experience_required, education_required,
             education_required_level, raw_text, created_at)
        VALUES (%s, %s, %s, %s, %s, %s, %s)
    """, (
        job.get("title"),
        json.dumps(job.get("required_skills") or []),
        job.get("experience_required") or 0,
        job.get("education_required"),
        job.get("education_required_level") or 0,
        job.get("raw_text"),
        datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    ))
    conn.commit()
    job_id = cursor.lastrowid
    cursor.close()
    conn.close()
    return job_id


def get_all_jobs():
    conn = get_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM job_postings ORDER BY created_at DESC")
    rows = cursor.fetchall()
    cursor.close()
    conn.close()
    for row in rows:
        row["required_skills"] = json.loads(row["required_skills"] or "[]")
    return rows


def get_job(job_id: int):
    conn = get_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM job_postings WHERE id = %s", (job_id,))
    row = cursor.fetchone()
    cursor.close()
    conn.close()
    if row:
        row["required_skills"] = json.loads(row["required_skills"] or "[]")
    return row


# ============================================================
# MATCH RESULTS (Milestone 2)
# ============================================================

def save_match_results(job_id: int, results_df):
    """Clears any previous matches for this job, then stores the new ranked
    results (one row per candidate) so they can be revisited without
    re-running the matching engine every time the page loads."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM match_results WHERE job_id = %s", (job_id,))

    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    for _, row in results_df.iterrows():
        cursor.execute("""
            INSERT INTO match_results
                (job_id, candidate_id, hiring_score, skill_score, experience_score,
                 education_score, matched_skills, missing_skills, created_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
        """, (
            job_id,
            row.get("candidate_id"),
            row.get("hiring_score"),
            row.get("skill_score"),
            row.get("experience_score"),
            row.get("education_score"),
            json.dumps(row.get("matched_skills") or []),
            json.dumps(row.get("missing_skills") or []),
            now,
        ))
    conn.commit()
    cursor.close()
    conn.close()


def get_matches_for_job(job_id: int):
    conn = get_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("""
        SELECT m.*, c.name, c.email
        FROM match_results m
        JOIN candidates c ON c.id = m.candidate_id
        WHERE m.job_id = %s
        ORDER BY m.hiring_score DESC
    """, (job_id,))
    rows = cursor.fetchall()
    cursor.close()
    conn.close()
    for row in rows:
        row["matched_skills"] = json.loads(row["matched_skills"] or "[]")
        row["missing_skills"] = json.loads(row["missing_skills"] or "[]")
    return rows


# ============================================================
# RECRUITER / ADMIN ACCOUNTS (login)
# ============================================================

def insert_recruiter(name: str, email: str, password_salt: str, password_hash: str,
                      role: str = "recruiter"):
    """Returns the new recruiter's id, or None if the email is already
    registered (relies on the UNIQUE constraint on email). role is
    'recruiter' or 'admin' -- public signup always passes 'recruiter';
    promote to admin via make_admin.py."""
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("""
            INSERT INTO recruiters (name, email, password_salt, password_hash, role, created_at)
            VALUES (%s, %s, %s, %s, %s, %s)
        """, (
            name, email, password_salt, password_hash, role,
            datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        ))
        conn.commit()
        return cursor.lastrowid
    except mysql_errors.IntegrityError:
        return None
    finally:
        cursor.close()
        conn.close()


def set_recruiter_role(email: str, role: str) -> bool:
    """Used by make_admin.py to promote/demote an existing account."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE recruiters SET role = %s WHERE email = %s", (role, email))
    conn.commit()
    updated = cursor.rowcount > 0
    cursor.close()
    conn.close()
    return updated


def get_recruiter_by_email(email: str):
    conn = get_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM recruiters WHERE email = %s", (email,))
    row = cursor.fetchone()
    cursor.close()
    conn.close()
    return row


def get_recruiter_by_id(recruiter_id: int):
    conn = get_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM recruiters WHERE id = %s", (recruiter_id,))
    row = cursor.fetchone()
    cursor.close()
    conn.close()
    return row


# ============================================================
# REMEMBER-ME TOKENS (recruiters/admins)
# ============================================================

def save_remember_token(recruiter_id: int, token_hash: str, expires_at: datetime):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO remember_tokens (recruiter_id, token_hash, expires_at, created_at)
        VALUES (%s, %s, %s, %s)
    """, (
        recruiter_id,
        token_hash,
        expires_at.strftime("%Y-%m-%d %H:%M:%S"),
        datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    ))
    conn.commit()
    cursor.close()
    conn.close()


def get_recruiter_by_token(token_hash: str):
    """Returns the recruiter dict if the token exists and hasn't expired,
    else None."""
    conn = get_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("""
        SELECT r.* FROM remember_tokens t
        JOIN recruiters r ON r.id = t.recruiter_id
        WHERE t.token_hash = %s AND t.expires_at > %s
    """, (token_hash, datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
    row = cursor.fetchone()
    cursor.close()
    conn.close()
    return row


def delete_remember_token(token_hash: str):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM remember_tokens WHERE token_hash = %s", (token_hash,))
    conn.commit()
    cursor.close()
    conn.close()


# ============================================================
# CANDIDATE ACCOUNTS (interview takers -- separate from recruiters)
# ============================================================

def insert_candidate_account(name: str, email: str, password_salt: str, password_hash: str):
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("""
            INSERT INTO candidate_accounts (name, email, password_salt, password_hash, created_at)
            VALUES (%s, %s, %s, %s, %s)
        """, (
            name, email, password_salt, password_hash,
            datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        ))
        conn.commit()
        return cursor.lastrowid
    except mysql_errors.IntegrityError:
        return None
    finally:
        cursor.close()
        conn.close()


def get_candidate_account_by_email(email: str):
    conn = get_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM candidate_accounts WHERE email = %s", (email,))
    row = cursor.fetchone()
    cursor.close()
    conn.close()
    return row


def get_candidate_account_by_id(candidate_account_id: int):
    conn = get_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM candidate_accounts WHERE id = %s", (candidate_account_id,))
    row = cursor.fetchone()
    cursor.close()
    conn.close()
    return row


def save_candidate_remember_token(candidate_account_id: int, token_hash: str, expires_at: datetime):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO candidate_remember_tokens (candidate_account_id, token_hash, expires_at, created_at)
        VALUES (%s, %s, %s, %s)
    """, (
        candidate_account_id,
        token_hash,
        expires_at.strftime("%Y-%m-%d %H:%M:%S"),
        datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    ))
    conn.commit()
    cursor.close()
    conn.close()


def get_candidate_account_by_token(token_hash: str):
    conn = get_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("""
        SELECT c.* FROM candidate_remember_tokens t
        JOIN candidate_accounts c ON c.id = t.candidate_account_id
        WHERE t.token_hash = %s AND t.expires_at > %s
    """, (token_hash, datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
    row = cursor.fetchone()
    cursor.close()
    conn.close()
    return row


def delete_candidate_remember_token(token_hash: str):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM candidate_remember_tokens WHERE token_hash = %s", (token_hash,))
    conn.commit()
    cursor.close()
    conn.close()