"""
job_parser.py
Turns a raw, pasted job-description text block into the structured
requirement dict the matching engine needs -- required_skills,
experience_required, education_required -- using the same NLP-style
approach as extractor.py (regex + shared skill taxonomy), so no one has to
hand-type a skills list for every posting.
"""

import re
from typing import Optional

from skills_taxonomy import extract_skills_from_text
from profile_utils import education_level

MIN_EXPERIENCE_RE = re.compile(r"(\d+(?:\.\d+)?)\s*\+?\s*years?", re.IGNORECASE)

DEGREE_RE = re.compile(
    r"\b(?:bachelor'?s?|master'?s?|b\.?tech|m\.?tech|b\.?e\.?|m\.?e\.?|bca|mca|"
    r"b\.?sc|m\.?sc|mba|ph\.?d|diploma)\b[^\n]{0,60}",
    re.IGNORECASE,
)


def _guess_title(text: str) -> Optional[str]:
    """Fall back to the first non-empty line if the user didn't type a
    title -- job descriptions are almost always headed with the role name."""
    if not text:
        return None
    for line in text.splitlines():
        line = line.strip()
        if line:
            return line[:120]
    return None


def extract_job_requirements(text: str, title: Optional[str] = None) -> dict:
    """Parse a job-description text block into a structured dict ready for
    db.insert_job() and matching_engine.calculate_match()."""
    required_skills = extract_skills_from_text(text)

    # take the HIGHEST "N years" figure mentioned, since postings often say
    # things like "2+ years in X, 5+ years overall" -- we want the overall bar
    years_found = [float(y) for y in MIN_EXPERIENCE_RE.findall(text or "")]
    experience_required = max(years_found) if years_found else 0.0

    degree_match = DEGREE_RE.search(text or "")
    education_text = degree_match.group(0).strip() if degree_match else ""

    job_title = (title or "").strip() or _guess_title(text) or "Untitled Position"

    return {
        "title": job_title,
        "required_skills": required_skills,
        "experience_required": experience_required,
        "education_required": education_text or "Not specified",
        "education_required_level": education_level(education_text),
        "raw_text": text,
    }
