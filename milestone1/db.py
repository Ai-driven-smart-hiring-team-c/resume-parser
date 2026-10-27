"""
db.py
Handles all database work for the Recruitment Copilot, using MySQL.
 
Requires a MySQL server running locally and the mysql-connector-python
package: pip install mysql-connector-python
"""
 
import os
import mysql.connector
from datetime import datetime
 
DB_HOST = "localhost"
DB_USER = "root"
DB_PASSWORD = os.environ.get("DB_PASSWORD", "244205")   # set DB_PASSWORD env var instead of editing this
DB_NAME = "recruitment_copilot"
 
 
def get_connection(with_database=True):
    return mysql.connector.connect(
        host=DB_HOST,
        user=DB_USER,
        password=DB_PASSWORD,
        database=DB_NAME if with_database else None,
    )
 
 
def init_db():
    conn = get_connection(with_database=False)
    cursor = conn.cursor()
    cursor.execute(f"CREATE DATABASE IF NOT EXISTS {DB_NAME}")
    cursor.close()
    conn.close()
 
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
    conn.commit()
 
    # Backward-compatible for databases created before the `summary`
    # column existed: add it if it isn't there yet.
    cursor.execute("""
        SELECT COUNT(*) FROM information_schema.columns
        WHERE table_schema = %s AND table_name = 'candidates' AND column_name = 'summary'
    """, (DB_NAME,))
    has_summary_column = cursor.fetchone()[0] > 0
    if not has_summary_column:
        cursor.execute("ALTER TABLE candidates ADD COLUMN summary TEXT")
        conn.commit()
 
    cursor.close()
    conn.close()
 
 
def insert_candidate(profile: dict):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO candidates
            (file_name, name, email, phone, location, education,
             experience, skills, certifications, projects, summary, raw_text, uploaded_at)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
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
        datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    ))
    conn.commit()
    cursor.close()
    conn.close()
 
 
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
 