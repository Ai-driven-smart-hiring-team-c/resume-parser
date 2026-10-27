"""
llm_skill_extractor.py
Optional, opt-in augmentation for skill extraction using a HuggingFace
zero-shot classifier. The taxonomy match in skills_taxonomy.py is fast and
covers the vocabulary you define -- this module exists for the case where a
resume or job description phrases a skill in a way the taxonomy doesn't
recognize (a niche tool, an unusual phrasing, etc.).

It is NOT called anywhere by default because loading a transformer model is
slow (multi-second cold start, real memory footprint) and unnecessary for
most documents. Wire it in only where you're willing to pay that cost --
e.g. job postings, since there are far fewer of those than resumes.

Requires: pip install transformers torch
"""

from typing import List

_classifier = None


def _get_classifier():
    global _classifier
    if _classifier is None:
        from transformers import pipeline  # imported lazily on purpose
        _classifier = pipeline("zero-shot-classification", model="facebook/bart-large-mnli")
    return _classifier


def get_noun_phrase_candidates(nlp_doc, known_skills: List[str]) -> List[str]:
    """Pull short noun phrases out of a spaCy doc that AREN'T already in the
    taxonomy match -- these are the candidates worth checking with the LLM."""
    known_lower = {s.lower() for s in known_skills}
    seen = set()
    candidates = []
    for chunk in nlp_doc.noun_chunks:
        phrase = chunk.text.strip()
        words = phrase.split()
        if 1 < len(words) <= 3 and phrase.lower() not in known_lower and phrase.lower() not in seen:
            seen.add(phrase.lower())
            candidates.append(phrase)
    return candidates


def extract_skills_llm(candidate_terms: List[str], threshold: float = 0.85) -> List[str]:
    """Classify each candidate noun-phrase as 'a professional skill or
    technology' vs not, keeping only confident positives. Capped at 30 terms
    per call to keep inference time bounded. Fails silently (returns []) if
    transformers/torch aren't installed, so callers never need a try/except."""
    if not candidate_terms:
        return []
    try:
        classifier = _get_classifier()
    except ImportError:
        return []

    labels = ["a professional skill or technology", "not a skill"]
    confirmed = []
    for term in candidate_terms[:30]:
        result = classifier(term, labels)
        if result["labels"][0] == labels[0] and result["scores"][0] >= threshold:
            confirmed.append(term)
    return confirmed
