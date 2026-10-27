"""
extractor.py
Structured field extraction using spaCy NER, fitted to the field names
db.py expects (file_name, name, email, phone, location, education,
experience, skills, certifications, projects, raw_text).

Setup (once):
    pip install spacy
    python -m spacy download en_core_web_sm
"""

import re
from datetime import datetime
from typing import Optional

import spacy

nlp = spacy.load("en_core_web_sm")

EMAIL_RE = re.compile(r"[\w\.-]+@[\w\.-]+")
PHONE_RE = re.compile(r"\+?\d[\d -]{8,}\d")
EXPERIENCE_RE = re.compile(r"(\d+(\.\d+)?)\s*\+?\s*years?", re.IGNORECASE)
DATE_RANGE_RE = re.compile(
    r"(20\d{2}|19\d{2})\s*(?:-|–|—|to)\s*(present|current|20\d{2}|19\d{2})",
    re.IGNORECASE,
)

SKILLS_LIST = [
    "Python", "Java", "SQL", "Machine Learning", "TensorFlow",
    "Project Management", "C++", "JavaScript", "React", "Node.js",
    "Deep Learning", "NLP", "Data Analysis", "Excel", "Power BI",
]

# Words that spaCy's small model frequently mis-tags as PERSON/GPE on resumes
# (skill names, section headers). Anything matching these (case-insensitive,
# whole match) is rejected as a candidate name or location.
NON_ENTITY_WORDS = {s.lower() for s in SKILLS_LIST} | {
    "objective", "summary", "experience", "education", "skills",
    "projects", "certifications", "profile", "contact", "resume", "cv",
    "work experience", "professional summary", "career objective",
    "matplotlib", "numpy", "pandas", "seaborn", "keras", "pytorch",
    "scikit-learn", "sklearn", "tableau", "power bi", "aws", "azure",
    "docker", "kubernetes", "git", "github", "gitlab", "linux", "html",
    "css", "mysql", "mongodb", "postgresql", "flask", "django", "linkedin",
}

# A resume's very first non-empty line is almost always the candidate's
# name (before contact details, objective, etc.). This is a far stronger
# signal than trusting wherever spaCy's small model happens to tag PERSON,
# which frequently misfires on tool/library names in body text.
# NOTE: deliberately NOT requiring every word to start with a capital
# letter — real-world resumes are inconsistently capitalized (e.g. "Om
# sandhan" with a lowercase surname), so this only checks the *shape*
# (short line, a couple of alphabetic words) and title-cases the result.
NAME_LINE_RE = re.compile(r"^[A-Za-z][a-zA-Z.'-]*(?:\s+[A-Za-z][a-zA-Z.'-]*){1,3}$")

# Common resume tagline/job-title words. A line containing any of these is
# almost certainly a headline ("Machine Learning Engineer") rather than a
# name, even though it superficially matches the Title Case pattern above.
TITLE_LINE_WORDS = {
    "engineer", "developer", "manager", "analyst", "scientist", "architect",
    "designer", "specialist", "consultant", "intern", "director", "lead",
    "administrator", "coordinator", "executive", "officer", "technician",
}

EDUCATION_KEYWORDS = ("university", "college", "institute", "school", "academy")
DEGREE_RE = re.compile(
    r"(?:bachelor|master|b\.?tech|m\.?tech|b\.?e\.?|m\.?e\.?|bca|mca|"
    r"b\.?sc|m\.?sc|mba|ph\.?d|diploma)[^\n]{0,60}",
    re.IGNORECASE,
)


def _is_real_entity(text: str) -> bool:
    return text.strip().lower() not in NON_ENTITY_WORDS


def _guess_experience_from_dates(text: str) -> Optional[str]:
    """Fallback when no explicit 'X years' phrase is found: infer a rough
    span from date ranges like '2019 - Present' or '2018-2022'."""
    matches = DATE_RANGE_RE.findall(text)
    if not matches:
        return None
    current_year = datetime.now().year
    years = []
    for start, end in matches:
        start_year = int(start)
        end_year = current_year if end.lower() in ("present", "current") else int(end)
        if end_year >= start_year:
            years.append((start_year, end_year))
    if not years:
        return None
    earliest = min(y[0] for y in years)
    latest = max(y[1] for y in years)
    span = latest - earliest
    if span <= 0:
        return None
    latest_label = "Present" if latest == current_year else str(latest)
    return f"~{span} years (est. from {earliest}-{latest_label})"


def _guess_name_from_header(text: str) -> Optional[str]:
    """The candidate's name is almost always the first non-empty line of a
    resume, above contact info. Check the first few lines for something
    that looks like 'First Last' (2-4 capitalized words, no digits/emails)."""
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    for line in lines[:3]:
        if "@" in line or any(ch.isdigit() for ch in line):
            continue
        if line.lower() in NON_ENTITY_WORDS:
            continue
        if any(word in line.lower().split() for word in TITLE_LINE_WORDS):
            continue
        if NAME_LINE_RE.match(line):
            return " ".join(w.capitalize() for w in line.split())
    return None


FILENAME_STRIP_WORDS = ("resume", "cv", "updated", "final", "latest", "new", "v1", "v2")


def _guess_name_from_filename(file_name: str) -> Optional[str]:
    """Last-resort fallback: many people literally name their file after
    themselves, e.g. 'Om_Sandhan_Resume.pdf' -> 'Om Sandhan'."""
    stem = re.sub(r"\.\w+$", "", file_name)
    stem = re.sub(r"[_\-]+", " ", stem).strip()
    words = [w for w in stem.split() if w.lower() not in FILENAME_STRIP_WORDS and not w.isdigit()]
    if 1 < len(words) <= 4 and all(w.isalpha() for w in words):
        return " ".join(w.capitalize() for w in words)
    return None


def extract_candidate_info(text: str, file_name: Optional[str] = None) -> dict:
    doc = nlp(text)
    candidate = {
        "name": None,
        "email": None,
        "phone": None,
        "location": None,
        "education": [],
        "skills": [],
        "experience": [],
        "certifications": [],
    }

    email_match = EMAIL_RE.search(text)
    if email_match:
        candidate["email"] = email_match.group(0)

    phone_match = PHONE_RE.search(text)
    if phone_match:
        candidate["phone"] = phone_match.group(0)

    # Resumes almost always put the candidate's name in the first line or
    # two, above contact details. Try that direct heuristic first since
    # it's more reliable than spaCy's small model, which can mis-tag tool
    # or library names (e.g. "Matplotlib") as PERSON anywhere in the text.
    header_name = _guess_name_from_header(text)
    if header_name:
        candidate["name"] = header_name
    else:
        best_name = None
        best_name_pos = None
        for ent in doc.ents:
            if ent.label_ == "PERSON" and _is_real_entity(ent.text):
                if best_name is None or ent.start_char < best_name_pos:
                    best_name = ent.text
                    best_name_pos = ent.start_char
        if best_name is not None:
            candidate["name"] = best_name

    if candidate["name"] is None and file_name:
        candidate["name"] = _guess_name_from_filename(file_name)

    for ent in doc.ents:
        if ent.label_ == "ORG":
            if any(kw in ent.text.lower() for kw in EDUCATION_KEYWORDS):
                candidate["education"].append(ent.text)
        elif ent.label_ == "GPE":
            if candidate["location"] is None and _is_real_entity(ent.text):
                candidate["location"] = ent.text
        elif ent.label_ == "WORK_OF_ART":
            candidate["certifications"].append(ent.text)

    # Fallback: regex-based degree detection when spaCy doesn't tag an ORG
    # (common when the school name sits on its own line with no verb/context
    # for the model to key off of).
    if not candidate["education"]:
        degree_match = DEGREE_RE.search(text)
        if degree_match:
            candidate["education"].append(degree_match.group(0).strip())

    candidate["skills"] = [
        skill for skill in SKILLS_LIST if skill.lower() in text.lower()
    ]

    exp_match = EXPERIENCE_RE.search(text)
    if exp_match:
        candidate["experience"].append(f"{exp_match.group(1)} years")
    else:
        guessed = _guess_experience_from_dates(text)
        if guessed:
            candidate["experience"].append(guessed)

    return candidate


def extract_fields(text: str, file_name: str) -> dict:
    candidate = extract_candidate_info(text, file_name)

    def join_or_default(items, default="Not found"):
        return ", ".join(items) if items else default

    name = candidate["name"] or "This candidate"
    education = join_or_default(candidate["education"], default=None)
    location = candidate["location"]
    skills = candidate["skills"]
    experience = join_or_default(candidate["experience"], default=None)

    clauses = []
    if education:
        clauses.append(f"holds a background in {education}")
    if location:
        clauses.append(f"is based in {location}")
    sentence_one = f"{name} " + " and ".join(clauses) + "." if clauses else f"{name}."

    sentence_two = None
    if skills:
        top_skills = ", ".join(skills[:5])
        sentence_two = f"Skilled in {top_skills}."
    if experience:
        exp_clause = f"Has {experience} of experience."
        sentence_two = f"{sentence_two} {exp_clause}" if sentence_two else exp_clause

    summary = sentence_one
    if sentence_two:
        summary += f" {sentence_two}"

    return {
        "file_name": file_name,
        "name": candidate["name"] or "Not found",
        "email": candidate["email"] or "Not found",
        "phone": candidate["phone"] or "Not found",
        "location": candidate["location"] or "Not found",
        "education": join_or_default(candidate["education"]),
        "experience": join_or_default(candidate["experience"]),
        "skills": join_or_default(candidate["skills"]),
        "certifications": join_or_default(candidate["certifications"]),
        "projects": "Not found",
        "summary": summary,
        "raw_text": text,
    }
