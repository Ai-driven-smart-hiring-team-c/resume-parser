"""
matching_engine.py
Milestone 2: Candidate-Job Matching & Skill-Gap Analysis.

calculate_match()   -> weighted hiring score for one candidate vs one job
skill_gap_report()  -> matched/missing skills + training recommendations
batch_match()       -> ranks every candidate against one job (DataFrame)

Scoring weights match the brief: skills 60%, experience 25%, education 15%.
"""

from typing import Dict, List

import pandas as pd

from profile_utils import extract_years, education_level

SKILL_WEIGHT = 0.60
EXPERIENCE_WEIGHT = 0.25
EDUCATION_WEIGHT = 0.15


def _as_skill_set(skills) -> set:
    """Accepts either a list (from job_parser / fresh extraction) or a
    comma-separated string (as stored in the candidates table)."""
    if isinstance(skills, (list, set, tuple)):
        return {s.strip() for s in skills if s and s.strip()}
    if isinstance(skills, str):
        return {s.strip() for s in skills.split(",") if s.strip() and s.strip().lower() != "not found"}
    return set()


def calculate_match(candidate: Dict, job: Dict) -> Dict:
    """
    candidate: dict with "skills" (list or comma-string), "experience"
               (free text, e.g. '5 years'), "education" (free text)
    job:       dict with "required_skills" (list), "experience_required"
               (number), and either "education_required_level" (int) or
               "education_required" (free text)
    """
    required_skills = _as_skill_set(job.get("required_skills"))
    candidate_skills = _as_skill_set(candidate.get("skills"))

    matched_skills = sorted(required_skills & candidate_skills)
    missing_skills = sorted(required_skills - candidate_skills)

    # if a job lists no required skills, don't penalize -- nothing to miss
    skill_score = (len(matched_skills) / len(required_skills)) if required_skills else 1.0

    candidate_years = extract_years(candidate.get("experience"))
    required_years = job.get("experience_required") or 0
    experience_score = min(candidate_years / required_years, 1.0) if required_years else 1.0

    candidate_edu_level = education_level(candidate.get("education"))
    required_edu_level = job.get("education_required_level")
    if required_edu_level is None:
        required_edu_level = education_level(job.get("education_required"))

    if not required_edu_level:
        education_score = 1.0
    elif candidate_edu_level >= required_edu_level:
        education_score = 1.0
    else:
        education_score = candidate_edu_level / required_edu_level if candidate_edu_level else 0.0

    hiring_score = round(
        (skill_score * SKILL_WEIGHT
         + experience_score * EXPERIENCE_WEIGHT
         + education_score * EDUCATION_WEIGHT) * 100,
        2,
    )

    return {
        "hiring_score": hiring_score,
        "skill_score": round(skill_score * 100, 2),
        "experience_score": round(experience_score * 100, 2),
        "education_score": round(education_score * 100, 2),
        "matched_skills": matched_skills,
        "missing_skills": missing_skills,
    }


def skill_gap_report(candidate: Dict, job: Dict) -> Dict:
    match = calculate_match(candidate, job)
    return {
        "candidate": candidate.get("name", "Unknown"),
        "job_title": job.get("title", "Unknown"),
        "hiring_score": match["hiring_score"],
        "matched_skills": match["matched_skills"],
        "missing_skills": match["missing_skills"],
        "recommendations": [f"Consider training in {skill}" for skill in match["missing_skills"]],
    }


def batch_match(candidates: List[Dict], job: Dict) -> pd.DataFrame:
    """Match every candidate against one job, ranked by hiring_score desc.
    This is what satisfies the 'skill-gap report generated for ALL
    evaluated candidates' success criterion -- every row has one."""
    rows = []
    for candidate in candidates:
        match = calculate_match(candidate, job)
        rows.append({
            "candidate_id": candidate.get("id"),
            "name": candidate.get("name", "Not found"),
            "email": candidate.get("email", "Not found"),
            "hiring_score": match["hiring_score"],
            "skill_score": match["skill_score"],
            "experience_score": match["experience_score"],
            "education_score": match["education_score"],
            "matched_skills": match["matched_skills"],
            "missing_skills": match["missing_skills"],
        })

    df = pd.DataFrame(rows)
    if not df.empty:
        df = df.sort_values("hiring_score", ascending=False).reset_index(drop=True)
    return df
