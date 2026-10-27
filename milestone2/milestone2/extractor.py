"""
extractor.py
Structured field extraction from resume text.

The text is first split into sections (Education, Experience, Projects,
Certifications, Skills ...) by looking for headings, and each field is then read
from the section where it belongs. That is what stops an employer such as
"CodeBridge Academy" being mistaken for a college, or dates in the Education
section being counted as work experience.

Field names match what db.py expects: file_name, name, email, phone, location,
education, experience, skills, certifications, projects, summary, raw_text.

spaCy is only a last-resort fallback now (name / location when the rules find
nothing) and is loaded lazily, so the rule-based path works without it.
"""

import re
from datetime import date
from typing import Dict, List, Optional, Tuple

from skills_taxonomy import extract_skills_from_text, SKILL_TAXONOMY

# ============================================================
# Patterns
# ============================================================

EMAIL_RE = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")
PHONE_RE = re.compile(r"\+?\d[\d\s\-().]{8,}\d")

_MONTHS = "jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec"
_DATE = (
    rf"(?:(?:{_MONTHS})[a-z]*\.?,?\s*(?:19|20)\d{{2}}"      # May 2026, Sept. 2024
    rf"|(?:0?[1-9]|1[0-2])/(?:19|20)\d{{2}}"                # 06/2024
    rf"|(?:19|20)\d{{2}})"                                  # 2024
)
_PRESENT = r"present|current|now|ongoing|till\s+date|to\s+date|today"
# "May 2026 - Remote": the part after the dash is not a date, so the end is left empty (= still ongoing)
RANGE_RE = re.compile(rf"(?P<s>{_DATE})\s*(?:-|\u2013|\u2014|to|until)\s*(?P<e>{_DATE}|{_PRESENT})?", re.I)
YEAR_RE = re.compile(r"(?<!\d)((?:19|20)\d{2})(?!\d)")

EXPLICIT_YEARS_RE = re.compile(
    r"(\d+(?:\.\d+)?)\s*\+?\s*(?:years?|yrs?)\s*(?:of\s+)?(?:[A-Za-z\-]+\s+){0,3}?experience", re.I)
EXPERIENCE_OF_RE = re.compile(r"experience\s*(?:of|:)\s*(\d+(?:\.\d+)?)\s*\+?\s*(?:years?|yrs?)", re.I)

INSTITUTION_RE = re.compile(
    r"\b(?:university|college|institute|institution|school|academy|polytechnic|vidyalaya|vidyapeeth|"
    r"iit|nit|iiit|campus)\b", re.I)
_DEGREE_WORDS = (
    r"bachelors?|masters?|b\.?\s?tech|m\.?\s?tech|bca|mca|b\.?\s?sc|m\.?\s?sc|b\.?\s?com|m\.?\s?com|"
    r"bba|mba|ph\.?\s?d|doctorate|diploma|hsc|ssc|pgdm|(?:12|10)th|higher secondary|secondary school|"
    r"intermediate|associate degree|b\.?a\.?|m\.?a\.?"
)
DEGREE_RE = re.compile(rf"\b(?:{_DEGREE_WORDS})\b", re.I)
DEGREE_UPPER_RE = re.compile(r"\b(?:B\.E\.?|M\.E\.?|BE|ME)\b")          # case-sensitive: "be"/"me" are normal words

# glued headings, e.g. "...FundamentalsTechnical Skills" when two PDF pages are joined without a newline
_GLUED_HEADING_RE = re.compile(
    r"(?<=[a-z0-9\)\.])(?=(?:Technical Skills|Core Skills|Key Skills|Skills|Education|Work Experience|"
    r"Professional Experience|Experience|Projects|Certifications|Certificates|Professional Summary|"
    r"Summary|Objective|Achievements)\b)")

HEADINGS = {
    "summary": {"summary", "professional summary", "career summary", "career objective", "objective",
                "profile", "professional profile", "about me", "about"},
    "education": {"education", "academic background", "academics", "academic qualification",
                  "academic qualifications", "educational qualification", "educational qualifications",
                  "education & training", "qualifications"},
    "experience": {"experience", "work experience", "professional experience", "work history",
                   "employment history", "employment", "internships", "internship experience", "internship",
                   "industry experience", "experience & internships", "relevant experience"},
    "projects": {"projects", "academic projects", "personal projects", "key projects", "selected projects",
                 "project work", "projects & research"},
    "skills": {"skills", "technical skills", "core skills", "key skills", "technical proficiency",
               "core competencies", "skills & tools", "skills and tools", "tools & technologies",
               "technologies", "technical expertise", "skills summary", "areas of expertise"},
    "certifications": {"certifications", "certification", "certificates", "licenses & certifications",
                       "licenses and certifications", "courses", "courses & certifications",
                       "training & certifications", "certifications & courses", "professional certifications"},
    "other": {"achievements", "awards", "awards & achievements", "honors", "honours", "extracurricular",
              "extracurricular activities", "activities", "interests", "hobbies", "languages", "references",
              "declaration", "personal details", "personal information", "publications", "volunteering",
              "positions of responsibility", "additional information"},
}
# "Skills: Python, SQL" on one line starts a section too. "Languages:" is NOT here on purpose,
# because inside Technical Skills it means programming languages.
INLINE_HEADINGS = {"summary", "objective", "career objective", "skills", "technical skills", "key skills",
                   "core skills", "certifications", "certificates"}

INDIAN_STATES = [
    "Andhra Pradesh", "Arunachal Pradesh", "Assam", "Bihar", "Chhattisgarh", "Goa", "Gujarat", "Haryana",
    "Himachal Pradesh", "Jharkhand", "Karnataka", "Kerala", "Madhya Pradesh", "Maharashtra", "Manipur",
    "Meghalaya", "Mizoram", "Nagaland", "Odisha", "Punjab", "Rajasthan", "Sikkim", "Tamil Nadu", "Telangana",
    "Tripura", "Uttar Pradesh", "Uttarakhand", "West Bengal", "Delhi", "Chandigarh", "Puducherry",
    "Jammu and Kashmir", "Ladakh",
]
COUNTRIES = ["India", "USA", "United States", "UK", "United Kingdom", "Canada", "Germany", "Singapore",
             "UAE", "United Arab Emirates", "Australia", "Netherlands", "France", "Ireland"]
_PLACE_TAIL = "|".join(re.escape(p) for p in sorted(INDIAN_STATES + COUNTRIES, key=len, reverse=True))
CITY_PLACE_RE = re.compile(
    rf"([A-Z][A-Za-z.\-]+(?:\s[A-Z][A-Za-z.\-]+){{0,2}}),\s*({_PLACE_TAIL})\b")

# Words spaCy's small model often mis-tags as PERSON on resumes (skill names, section headers).
NON_ENTITY_WORDS = {alias.lower() for aliases in SKILL_TAXONOMY.values() for alias in aliases} | {
    s.lower() for s in SKILL_TAXONOMY.keys()
} | {
    "objective", "summary", "experience", "education", "skills", "projects", "certifications", "profile",
    "contact", "resume", "cv", "curriculum vitae", "work experience", "professional summary",
    "career objective", "linkedin", "github",
}
NAME_LINE_RE = re.compile(r"^[A-Za-z][a-zA-Z.'-]*(?:\s+[A-Za-z][a-zA-Z.'-]*){1,3}$")
TITLE_LINE_WORDS = {
    "engineer", "developer", "manager", "analyst", "scientist", "architect", "designer", "specialist",
    "consultant", "intern", "director", "lead", "administrator", "coordinator", "executive", "officer",
    "technician", "student", "fresher",
}
FILENAME_STRIP_WORDS = ("resume", "cv", "updated", "final", "latest", "new", "v1", "v2")

_nlp = None


def _get_nlp():
    """spaCy, loaded on first use. Returns None when it is not installed."""
    global _nlp
    if _nlp is None:
        try:
            import spacy
            _nlp = spacy.load("en_core_web_sm")
        except Exception:
            _nlp = False
    return _nlp or None


# ============================================================
# Text preparation + sections
# ============================================================

def _clean(value: str) -> str:
    return re.sub(r"\s+", " ", value or "").strip(" \t|\u2022\u00b7-\u2013\u2014,;:")


def _normalize(text: str) -> str:
    text = (text or "").replace("\r\n", "\n").replace("\r", "\n").replace("\f", "\n").replace("\u00a0", " ")
    text = _GLUED_HEADING_RE.sub("\n", text)
    return text


def _is_bullet(line: str) -> bool:
    return bool(re.match(r"^\s*[\u2022\u00b7\u25aa\u25cf\u25e6\u2023*\-\u2013]\s+\S", line))


def _heading_key(line: str) -> Optional[str]:
    clean = re.sub(r"[^a-z& ]", " ", line.lower())
    clean = re.sub(r"\s+", " ", clean).strip()
    if not clean or len(clean) > 40:
        return None
    for key, names in HEADINGS.items():
        if clean in names:
            return key
    return None


def _split_sections(text: str) -> Dict[str, List[str]]:
    sections: Dict[str, List[str]] = {"header": []}
    current = "header"
    for raw in text.split("\n"):
        line = raw.strip()
        if not line:
            continue
        key = _heading_key(line)
        if key:
            current = key
            sections.setdefault(key, [])
            continue
        inline = re.match(r"^([A-Za-z &]{3,30}?)\s*:\s*(\S.*)$", line)
        if inline:
            label = re.sub(r"\s+", " ", inline.group(1).lower()).strip()
            if label in INLINE_HEADINGS:
                key = _heading_key(label) or ("summary" if label == "objective" else None)
                if key:
                    current = key
                    sections.setdefault(key, []).append(inline.group(2).strip())
                    continue
        sections[current].append(line)
    return sections


# ============================================================
# Contact details + name
# ============================================================

def _find_email(text: str) -> Optional[str]:
    m = EMAIL_RE.search(text)
    return m.group(0) if m else None


def _find_phone(header_lines: List[str], text: str) -> Optional[str]:
    """First number with 10-13 digits, looking at the top of the resume first
    (a year range such as '2019 - 2023' has too few digits to be mistaken for one)."""
    for blob in ("\n".join(header_lines[:8]), text):
        for m in PHONE_RE.finditer(blob):
            digits = re.sub(r"\D", "", m.group(0))
            if 10 <= len(digits) <= 13:
                return m.group(0).strip()
    return None


def _guess_name_from_header(lines: List[str]) -> Optional[str]:
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


def _guess_name_from_filename(file_name: str) -> Optional[str]:
    stem = re.sub(r"\.\w+$", "", file_name or "")
    stem = re.sub(r"[_\-]+", " ", stem).strip()
    words = [w for w in stem.split() if w.lower() not in FILENAME_STRIP_WORDS and not w.isdigit()]
    if 1 < len(words) <= 4 and all(w.isalpha() for w in words):
        return " ".join(w.capitalize() for w in words)
    return None


def _find_name(header_lines: List[str], text: str, file_name: Optional[str]) -> Optional[str]:
    name = _guess_name_from_header(header_lines)
    if name:
        return name
    nlp = _get_nlp()
    if nlp is not None:
        for ent in nlp(text[:3000]).ents:
            if ent.label_ == "PERSON" and ent.text.strip().lower() not in NON_ENTITY_WORDS:
                return ent.text.strip()
    return _guess_name_from_filename(file_name) if file_name else None


# ============================================================
# Location
# ============================================================

def _city_place(line: str) -> Optional[str]:
    m = CITY_PLACE_RE.search(line)
    if not m:
        return None
    words = m.group(1).split()
    for i in range(len(words) - 1, -1, -1):            # "Patil College Nashik" -> "Nashik"
        if INSTITUTION_RE.fullmatch(words[i]):
            words = words[i + 1:]
            break
    return f"{' '.join(words)}, {m.group(2)}" if words else None


def _find_location(header_lines: List[str], text: str) -> Optional[str]:
    for line in text.split("\n")[:30]:                                   # 1. an explicit label
        m = re.match(r"^\s*(?:current\s+)?(?:location|address|city|based in)\s*[:\-]\s*(.+)$", line, re.I)
        if m:
            return _clean(m.group(1))[:80] or None
    for line in header_lines[:8]:                                        # 2. contact block at the top
        place = _city_place(line)
        if place:
            return place
    place = _city_place(text)                                            # 3. first "City, State" anywhere
    if place:
        return place
    nlp = _get_nlp()                                                     # 4. last resort
    if nlp is not None:
        for ent in nlp(text[:3000]).ents:
            if ent.label_ == "GPE" and ent.text.strip().lower() not in NON_ENTITY_WORDS:
                return ent.text.strip()
    return None


# ============================================================
# Dates + experience
# ============================================================

_MONTH_NUM = {m: i for i, m in enumerate(_MONTHS.split("|"), 1)}


def _parse_date(token: str, is_end: bool, today: date) -> Optional[Tuple[int, int]]:
    t = token.strip().lower()
    if re.fullmatch(_PRESENT, t):
        return today.year, today.month
    m = re.match(rf"({_MONTHS})[a-z]*\.?,?\s*((?:19|20)\d{{2}})", t)
    if m:
        return int(m.group(2)), _MONTH_NUM[m.group(1)]
    m = re.match(r"(\d{1,2})/((?:19|20)\d{2})", t)
    if m:
        return int(m.group(2)), int(m.group(1))
    if re.fullmatch(r"(?:19|20)\d{2}", t):
        return int(t), (12 if is_end else 1)
    return None


def _next_text_line(lines: List[str], idx: int) -> str:
    for line in lines[idx + 1: idx + 3]:
        if _is_bullet(line) or RANGE_RE.search(line):
            return ""
        if len(line.split()) <= 10:
            return line
    return ""


def _strip_title(value: str) -> str:
    value = re.sub(r"\(\s*$", "", value.strip())
    value = re.sub(r"\b(?:from|since|during|between|w\.e\.f\.?)\s*$", "", value.strip(), flags=re.I)
    return _clean(value)


def _parse_experience(lines: List[str], today: date):
    """Returns (merged month count, [role strings]) from dated entries.
    A virtual internship counts as one month."""
    today_idx = today.year * 12 + today.month
    intervals, roles = [], []
    for idx, line in enumerate(lines):
        if _is_bullet(line):
            continue
        m = RANGE_RE.search(line)
        if not m:
            continue
        start = _parse_date(m.group("s"), False, today)
        end = _parse_date(m.group("e"), True, today) if m.group("e") else (today.year, today.month)
        if not start or not end:
            continue
        s_idx = start[0] * 12 + start[1]
        e_idx = min(end[0] * 12 + end[1], today_idx)
        if e_idx < s_idx:
            continue

        title = _strip_title(line[:m.start()])
        org = ""
        if title:
            org_line = _next_text_line(lines, idx)
            org = _clean(re.split(r"\s*[\u2014\u2013|,]\s*", org_line)[0]) if org_line else ""
            if re.fullmatch(r"(?:virtual\s+)?(?:internship|experience|program|training|job)", org, re.I):
                org = ""
        else:                                            # date sits on its own line: title is the line above
            prev = next((l for l in reversed(lines[:idx]) if not _is_bullet(l) and not RANGE_RE.search(l)), "")
            title = _clean(prev)

        context = " ".join([line, org] + lines[idx + 1: idx + 3]).lower()
        if "virtual" in context:
            e_idx = s_idx
        intervals.append((s_idx, e_idx))
        if title:
            role = f"{title} at {org}" if org and org.lower() not in title.lower() else title
            if role not in roles:
                roles.append(role)

    total, last_end = 0, None
    for s_idx, e_idx in sorted(intervals):
        if last_end is None or s_idx > last_end:
            total += e_idx - s_idx + 1
            last_end = e_idx
        elif e_idx > last_end:
            total += e_idx - last_end
            last_end = e_idx
    return total, roles


def _explicit_years(text: str) -> Optional[float]:
    found = [float(x) for x in EXPLICIT_YEARS_RE.findall(text)] + [float(x) for x in EXPERIENCE_OF_RE.findall(text)]
    return max(found) if found else None


def _format_experience(explicit: Optional[float], months: int, roles: List[str]) -> Optional[str]:
    if explicit is not None:
        head = f"{explicit:g} years"
    elif months:
        head = f"{months / 12:.1f} years" if months >= 12 else f"~{months / 12:.1f} years ({months} months)"
    else:
        return None
    return f"{head}: {'; '.join(roles[:4])}" if roles else head


# ============================================================
# Education, projects, certifications, skills
# ============================================================

def _has_degree(text: str) -> bool:
    return bool(DEGREE_RE.search(text) or DEGREE_UPPER_RE.search(text))


def _parse_education(lines: List[str]) -> List[str]:
    entries, cur = [], {"degree": None, "institution": None, "years": None}

    def push():
        nonlocal cur
        if cur["degree"] or cur["institution"]:
            entries.append(dict(cur))
        cur = {"degree": None, "institution": None, "years": None}

    for line in lines:
        years = None
        m = RANGE_RE.search(line)
        if m:
            years = re.sub(r"\s+", " ", m.group(0)).strip(" -\u2013\u2014")
            line = line[:m.start()] + " " + line[m.end():]
        else:
            ys = YEAR_RE.findall(line)
            if ys:
                years = ys[-1]
                line = YEAR_RE.sub(" ", line)
        line = re.sub(r"\(\s*\)", " ", line)
        for part in re.split(r"\s*[|\u2014\u2013]\s*|\s{2,}", line):
            part = _clean(part)
            if not part:
                continue
            if _has_degree(part):
                kind = "degree"
            elif INSTITUTION_RE.search(part):
                kind = "institution"
            else:
                continue                                    # a city, a CGPA, a stray word
            if cur[kind]:
                push()
            cur[kind] = part
        if years and not cur["years"] and (cur["degree"] or cur["institution"]):
            cur["years"] = years
    push()

    out = []
    for e in entries:
        text = ", ".join(p for p in (e["degree"], e["institution"]) if p)
        out.append(f"{text} ({e['years']})" if e["years"] else text)
    return out


_STACK_LINE_RE = re.compile(
    r"^(?:tech(?:nologies)?(?:\s*stack)?|tools?|stack|built with|technologies used)\s*[:\-]", re.I)


def _parse_projects(lines: List[str]) -> List[str]:
    titles = []
    for line in lines:
        if _is_bullet(line) or _STACK_LINE_RE.match(line):
            continue
        title = _clean(re.split(r"\s*[|\u2014\u2013]\s*", RANGE_RE.sub("", line))[0])
        title = re.sub(r"\(\s*\)", "", title).strip()
        if 3 <= len(title) <= 90 and title not in titles:
            titles.append(title)
    return titles[:8]


def _parse_certifications(lines: List[str]) -> List[str]:
    items = []
    for line in lines:
        line = re.sub(r"^\s*[\u2022\u00b7\u25aa\u25cf\u25e6\u2023*\-\u2013]\s*", "", line)
        for part in re.split(r"\s*\|\s*|\s+[\u2022\u00b7]\s+", line):
            part = re.sub(r"[\(\[]?\b(?:19|20)\d{2}\b[\)\]]?\s*$", "", part).strip()
            part = _clean(part)
            if 3 <= len(part) <= 120 and part not in items:
                items.append(part)
    return items[:15]


_SKILL_LABEL_STOP = {"tools", "skills", "other", "misc", "etc"}


def _skill_extras(lines: List[str], known_lower: set) -> List[str]:
    """Skills listed in the Skills section that the taxonomy does not know, kept as written."""
    extras = []
    for line in lines:
        label, sep, rest = line.partition(":")
        body = rest if sep and len(label.split()) <= 4 else line
        for token in re.split(r"[,;|\u2022\u00b7]", body):
            token = _clean(token)
            if not (2 <= len(token) <= 40) or len(token.split()) > 4 or token.lower() in _SKILL_LABEL_STOP:
                continue
            if token.isdigit() or extract_skills_from_text(token) or token.lower() in known_lower:
                continue
            token = token.title() if token.islower() else token
            if token.lower() not in {e.lower() for e in extras}:
                extras.append(token)
    return extras


# ============================================================
# Public API
# ============================================================

def _summary_text(sections: Dict[str, List[str]]) -> Optional[str]:
    lines = sections.get("summary") or []
    if not lines:
        return None
    text = re.sub(r"\s+", " ", " ".join(lines)).strip()
    if len(text) > 500:
        cut = text[:500]
        text = cut[: cut.rfind(".") + 1] or cut
    return text or None


def extract_candidate_info(text: str, file_name: Optional[str] = None, today: Optional[date] = None) -> dict:
    today = today or date.today()
    text = _normalize(text)
    sections = _split_sections(text)
    header = sections["header"]

    # fields that live in a section
    education = _parse_education(sections["education"]) if sections.get("education") else []
    if not education:                                    # no Education heading: look at the loose lines
        loose = header[2:] + sections.get("other", [])
        education = _parse_education([l for l in loose if _has_degree(l) or INSTITUTION_RE.search(l)])

    if sections.get("experience"):
        months, roles = _parse_experience(sections["experience"], today)
    else:                                                # no Experience heading: dated lines that are not education
        loose = [l for l in header[2:] + sections.get("other", []) if not (_has_degree(l) or INSTITUTION_RE.search(l))]
        months, roles = _parse_experience(loose, today)
    experience = _format_experience(_explicit_years(text), months, roles)

    certifications = _parse_certifications(sections.get("certifications", []))
    projects = _parse_projects(sections.get("projects", []))

    skills = extract_skills_from_text(text)
    skills += _skill_extras(sections.get("skills", []), {s.lower() for s in skills})

    return {
        "name": _find_name(header, text, file_name),
        "email": _find_email(text),
        "phone": _find_phone(header, text),
        "location": _find_location(header, text),
        "education": education,
        "experience": experience,
        "skills": skills,
        "certifications": certifications,
        "projects": projects,
        "summary_section": _summary_text(sections),
    }


def extract_fields(text: str, file_name: str, today: Optional[date] = None) -> dict:
    c = extract_candidate_info(text, file_name, today)

    name = c["name"] or "This candidate"
    first_education = c["education"][0] if c["education"] else None
    clauses = []
    if first_education:
        clauses.append(f"studied {first_education}")
    if c["location"]:
        clauses.append(f"is based in {c['location']}")
    generated = f"{name} " + " and ".join(clauses) + "." if clauses else f"{name}."
    if c["skills"]:
        generated += f" Skilled in {', '.join(c['skills'][:5])}."
    if c["experience"]:
        generated += f" Experience: {c['experience'].split(':')[0]}."

    return {
        "file_name": file_name,
        "name": c["name"] or "Not found",
        "email": c["email"] or "Not found",
        "phone": c["phone"] or "Not found",
        "location": c["location"] or "Not found",
        "education": "; ".join(c["education"]) or "Not found",
        "experience": c["experience"] or "Not found",
        "skills": ", ".join(c["skills"]) or "Not found",
        "certifications": ", ".join(c["certifications"]) or "Not found",
        "projects": "; ".join(c["projects"]) or "Not found",
        "summary": c["summary_section"] or generated,
        "raw_text": text,
    }