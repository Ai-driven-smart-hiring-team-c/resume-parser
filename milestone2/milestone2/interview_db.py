"""
interview_db.py
Database tables + helper functions for Milestone 3 (interview sessions,
questions, and candidate answers). Import init_interview_tables() and call
it once alongside init_db() in app.py.

Tables:
  interview_sessions   -- one row per interview (candidate + role + recruiter)
  interview_questions  -- generated questions for a session, with review status
  interview_answers    -- candidate's submitted answer per question
"""

from datetime import datetime
from db import get_connection


def init_interview_tables():
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS interview_sessions (
            id                  INT AUTO_INCREMENT PRIMARY KEY,
            candidate_account_id INT,
            job_role            VARCHAR(255),
            difficulty          VARCHAR(20),
            created_by_recruiter_id INT,
            status              VARCHAR(20) DEFAULT 'pending_review',
            created_at          DATETIME,
            FOREIGN KEY (candidate_account_id) REFERENCES candidate_accounts(id) ON DELETE CASCADE,
            FOREIGN KEY (created_by_recruiter_id) REFERENCES recruiters(id) ON DELETE SET NULL
        )
    """)
    # status: 'pending_review' (recruiter still reviewing questions) ->
    #         'ready' (candidate can take it) ->
    #         'completed' (candidate submitted all answers)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS interview_questions (
            id              INT AUTO_INCREMENT PRIMARY KEY,
            session_id      INT,
            question_text   TEXT,
            question_type   VARCHAR(20),
            order_index     INT,
            reviewed        BOOLEAN DEFAULT FALSE,
            FOREIGN KEY (session_id) REFERENCES interview_sessions(id) ON DELETE CASCADE
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS interview_answers (
            id              INT AUTO_INCREMENT PRIMARY KEY,
            question_id     INT,
            answer_text     TEXT,
            audio_data      LONGBLOB NULL,
            submitted_at    DATETIME,
            FOREIGN KEY (question_id) REFERENCES interview_questions(id) ON DELETE CASCADE
        )
    """)

    # Questions already generated for a role, reused so the AI does not run again
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS question_cache (
            id              INT AUTO_INCREMENT PRIMARY KEY,
            role_key        VARCHAR(255),
            question_type   VARCHAR(20),
            difficulty      VARCHAR(20),
            question_text   TEXT,
            source          VARCHAR(20),
            created_at      DATETIME,
            INDEX idx_question_cache_lookup (role_key, question_type, difficulty)
        )
    """)

    conn.commit()

    # Backward-compatible: add audio_data if an older DB predates it.
    cursor.execute("""
        SELECT COUNT(*) FROM information_schema.columns
        WHERE table_schema = DATABASE() AND table_name = 'interview_answers' AND column_name = 'audio_data'
    """)
    if cursor.fetchone()[0] == 0:
        cursor.execute("ALTER TABLE interview_answers ADD COLUMN audio_data LONGBLOB NULL")
        conn.commit()

    cursor.close()
    conn.close()


# ============================================================
# SESSIONS (created by recruiter)
# ============================================================

def create_interview_session(candidate_account_id, job_role, difficulty, recruiter_id):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO interview_sessions
            (candidate_account_id, job_role, difficulty, created_by_recruiter_id, status, created_at)
        VALUES (%s, %s, %s, %s, 'pending_review', %s)
    """, (
        candidate_account_id, job_role, difficulty, recruiter_id,
        datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    ))
    conn.commit()
    session_id = cursor.lastrowid
    cursor.close()
    conn.close()
    return session_id


def add_question(session_id, question_text, question_type, order_index):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO interview_questions (session_id, question_text, question_type, order_index, reviewed)
        VALUES (%s, %s, %s, %s, FALSE)
    """, (session_id, question_text, question_type, order_index))
    conn.commit()
    qid = cursor.lastrowid
    cursor.close()
    conn.close()
    return qid


def get_questions_for_session(session_id):
    conn = get_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("""
        SELECT * FROM interview_questions WHERE session_id = %s ORDER BY order_index
    """, (session_id,))
    rows = cursor.fetchall()
    cursor.close()
    conn.close()
    return rows


def mark_question_reviewed(question_id, reviewed=True):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE interview_questions SET reviewed = %s WHERE id = %s", (reviewed, question_id))
    conn.commit()
    cursor.close()
    conn.close()


def update_question_text(question_id, new_text):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE interview_questions SET question_text = %s WHERE id = %s", (new_text, question_id))
    conn.commit()
    cursor.close()
    conn.close()


def set_session_status(session_id, status):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE interview_sessions SET status = %s WHERE id = %s", (status, session_id))
    conn.commit()
    cursor.close()
    conn.close()


def get_sessions_for_recruiter(recruiter_id):
    conn = get_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("""
        SELECT s.*, c.name AS candidate_name, c.email AS candidate_email
        FROM interview_sessions s
        JOIN candidate_accounts c ON c.id = s.candidate_account_id
        WHERE s.created_by_recruiter_id = %s
        ORDER BY s.created_at DESC
    """, (recruiter_id,))
    rows = cursor.fetchall()
    cursor.close()
    conn.close()
    return rows


def get_session(session_id):
    conn = get_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM interview_sessions WHERE id = %s", (session_id,))
    row = cursor.fetchone()
    cursor.close()
    conn.close()
    return row


def get_recent_sessions(limit=8):
    """Latest interview sessions (any recruiter) with the candidate's name,
    for the dashboard's 'Recent Interviews' table."""
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


def get_interview_status_counts():
    """Counts of interview sessions by status, for the dashboard."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT status, COUNT(*) FROM interview_sessions GROUP BY status")
    rows = cursor.fetchall()
    cursor.close()
    conn.close()
    counts = {"pending_review": 0, "ready": 0, "completed": 0}
    for status, count in rows:
        counts[status] = count
    return counts


# ============================================================
# QUESTION CACHE (reuse questions already generated for a role)
# ============================================================

def _role_key(job_role: str) -> str:
    return " ".join((job_role or "").lower().split())


def get_cached_questions(job_role, question_type, difficulty, limit):
    """Up to `limit` previously generated questions for this role/type/difficulty, in random order."""
    if limit <= 0:
        return []
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT question_text FROM question_cache
        WHERE role_key = %s AND question_type = %s AND difficulty = %s
        ORDER BY RAND() LIMIT %s
        """,
        (_role_key(job_role), question_type, difficulty, int(limit)),
    )
    rows = [r[0] for r in cursor.fetchall()]
    cursor.close()
    conn.close()
    return rows


def save_cached_questions(job_role, question_type, difficulty, questions, source):
    """Stores AI-generated questions for later reuse; duplicates are skipped."""
    if not questions:
        return
    conn = get_connection()
    cursor = conn.cursor()
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    key = _role_key(job_role)
    for text in questions:
        cursor.execute(
            """
            SELECT 1 FROM question_cache
            WHERE role_key = %s AND question_type = %s AND difficulty = %s AND question_text = %s LIMIT 1
            """,
            (key, question_type, difficulty, text),
        )
        if cursor.fetchone():
            continue
        cursor.execute(
            """
            INSERT INTO question_cache (role_key, question_type, difficulty, question_text, source, created_at)
            VALUES (%s, %s, %s, %s, %s, %s)
            """,
            (key, question_type, difficulty, text, source, now),
        )
    conn.commit()
    cursor.close()
    conn.close()


# ============================================================
# CANDIDATE SIDE
# ============================================================

def get_sessions_for_candidate(candidate_account_id):
    """Only sessions with status='ready' or 'completed' -- pending_review
    sessions aren't visible to the candidate yet."""
    conn = get_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("""
        SELECT * FROM interview_sessions
        WHERE candidate_account_id = %s AND status IN ('ready', 'completed')
        ORDER BY created_at DESC
    """, (candidate_account_id,))
    rows = cursor.fetchall()
    cursor.close()
    conn.close()
    return rows


def submit_answer(question_id, answer_text, audio_data=None):
    """audio_data: optional raw WAV bytes of the candidate's spoken answer,
    so the recruiter can play it back later alongside the transcript."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO interview_answers (question_id, answer_text, audio_data, submitted_at)
        VALUES (%s, %s, %s, %s)
    """, (question_id, answer_text, audio_data, datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
    conn.commit()
    cursor.close()
    conn.close()


def get_answer_for_question(question_id):
    conn = get_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM interview_answers WHERE question_id = %s", (question_id,))
    row = cursor.fetchone()
    cursor.close()
    conn.close()
    return row


def get_answers_for_session(session_id):
    """Recruiter-facing: every question in the session, joined with its
    answer text AND the raw voice recording (if the candidate spoke their
    answer) so the recruiter can play it back."""
    conn = get_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("""
        SELECT q.id AS question_id, q.question_text, q.question_type, q.order_index,
               a.answer_text, a.audio_data, a.submitted_at
        FROM interview_questions q
        LEFT JOIN interview_answers a ON a.question_id = q.id
        WHERE q.session_id = %s
        ORDER BY q.order_index
    """, (session_id,))
    rows = cursor.fetchall()
    cursor.close()
    conn.close()
    return rows