"""
profile_utils.py
Small parsing helpers shared between candidate profiles and job postings so
"5 years" / "MS Computer Science" style free text can be compared numerically
by the matching engine.
"""

import re
from typing import Optional

YEARS_RE = re.compile(r"(\d+(?:\.\d+)?)\s*\+?\s*years?", re.IGNORECASE)

# ordered low -> high; matched as whole words/abbreviations so "M.Tech", "MSc",
# "Master's" etc. all resolve to the same level, while "ms" no longer fires
# inside words such as "Systems" or "Programs"
EDUCATION_LEVELS = {
    "diploma": 1,
    "bachelor": 2, "b.tech": 2, "btech": 2, "b.sc": 2, "bsc": 2,
    "bca": 2, "b.e": 2, "be": 2, "b.a": 2,
    "master": 3, "m.tech": 3, "mtech": 3, "m.sc": 3, "msc": 3,
    "mca": 3, "mba": 3, "m.e": 3, "ms": 3, "m.a": 3,
    "phd": 4, "ph.d": 4, "doctorate": 4,
}

_EDUCATION_PATTERNS = [
    (re.compile(r"(?<![a-z0-9])" + re.escape(keyword) + r"(?![a-z0-9])"), level)
    for keyword, level in EDUCATION_LEVELS.items()
]


def extract_years(text: Optional[str]) -> float:
    """Pull the first 'N years' style figure out of free text. Returns 0.0
    if nothing is found (e.g. 'Not found', None, empty string)."""
    if not text:
        return 0.0
    match = YEARS_RE.search(str(text))
    if not match:
        return 0.0
    try:
        return float(match.group(1))
    except ValueError:
        return 0.0


def education_level(text: Optional[str]) -> int:
    """Map free-text education info to a comparable level: 0 (unknown),
    1 (diploma), 2 (bachelor's), 3 (master's), 4 (phd)."""
    if not text:
        return 0
    lowered = str(text).lower()
    best = 0
    for pattern, level in _EDUCATION_PATTERNS:
        if level > best and pattern.search(lowered):
            best = level
    return best