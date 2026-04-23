from __future__ import annotations

import re
from typing import Dict, List, Tuple

from .models import JobListing


DEFAULT_INTERNSHIP_TERMS = [
    "intern",
    "internship",
    "summer analyst",
    "summer intern",
    "apprentice",
    "co-op",
]

DEFAULT_ROLE_TERMS = [
    "product",
    "product manager",
    "program",
    "business analyst",
    "operations",
    "strategy",
    "growth",
    "ai",
    "analytics",
    "research",
]

DEFAULT_AI_TERMS = ["ai", "machine learning", "llm", "genai", "artificial intelligence", "data"]


def _contains_any(text: str, keywords: List[str]) -> Tuple[bool, List[str]]:
    hits: List[str] = []
    haystack = text.lower()
    for term in keywords:
        token = (term or "").strip().lower()
        if not token:
            continue

        escaped = re.escape(token).replace(r"\ ", r"\s+")
        pattern = re.compile(rf"(?<!\w){escaped}(?!\w)")
        if pattern.search(haystack):
            hits.append(term)

    return (len(hits) > 0), hits


def is_target_listing(listing: JobListing, targets: Dict[str, List[str]]) -> bool:
    title = listing.role.lower()
    text = f"{listing.role} {listing.description}".lower()

    internship_terms = targets.get("internship_keywords", DEFAULT_INTERNSHIP_TERMS)
    role_terms = targets.get("role_keywords", DEFAULT_ROLE_TERMS)
    excluded_terms = targets.get("excluded_keywords", [])

    internship_hit, _ = _contains_any(text, internship_terms)
    internship_title_hit, _ = _contains_any(title, internship_terms)
    role_title_hit, _ = _contains_any(title, role_terms)

    if any(term.lower() in text for term in excluded_terms):
        return False

    require_intern = targets.get("require_internship_keyword", True)
    if require_intern and not internship_hit:
        return False

    return role_title_hit or internship_title_hit


def score_listing(listing: JobListing, targets: Dict[str, List[str]]) -> Tuple[int, str, List[str]]:
    text = f"{listing.role} {listing.description}".lower()
    title = listing.role.lower()
    location = listing.location.lower()

    internship_terms = targets.get("internship_keywords", DEFAULT_INTERNSHIP_TERMS)
    role_terms = targets.get("role_keywords", DEFAULT_ROLE_TERMS)
    ai_terms = targets.get("ai_keywords", DEFAULT_AI_TERMS)
    preferred_locations = [loc.lower() for loc in targets.get("preferred_locations", [])]
    company_priority = [name.lower() for name in targets.get("company_priority", [])]

    score = 0
    reasons: List[str] = []
    matched_keywords: List[str] = []

    internship_hit, internship_matches = _contains_any(text, internship_terms)
    if internship_hit:
        score += 35
        reasons.append("internship keyword")
        matched_keywords.extend(internship_matches)

    title_role_hit, title_role_matches = _contains_any(title, role_terms)
    if title_role_hit:
        score += 25
        reasons.append("role keyword in title")
        matched_keywords.extend(title_role_matches)

    desc_role_hit, desc_role_matches = _contains_any(text, role_terms)
    if desc_role_hit:
        score += 15
        reasons.append("role keyword in description")
        matched_keywords.extend(desc_role_matches)

    ai_hit, ai_matches = _contains_any(text, ai_terms)
    if ai_hit:
        score += 10
        reasons.append("AI relevance")
        matched_keywords.extend(ai_matches)

    if preferred_locations and any(loc in location for loc in preferred_locations):
        score += 10
        reasons.append("preferred location")

    if company_priority and listing.company.lower() in company_priority:
        score += 10
        reasons.append("priority company")

    if listing.apply_url:
        score += 5

    return min(score, 100), ", ".join(reasons), sorted(set(matched_keywords))


def choose_role_track(listing: JobListing, role_tracks: Dict[str, Dict]) -> Tuple[str, Dict]:
    if not role_tracks:
        return "general", {}

    text = f"{listing.role} {listing.description}".lower()
    best_name = "general"
    best_cfg: Dict = {}
    best_hits = -1

    for track_key, track_cfg in role_tracks.items():
        keywords = [term.lower() for term in track_cfg.get("match_keywords", [])]
        hits = sum(1 for keyword in keywords if keyword in text)
        if hits > best_hits:
            best_hits = hits
            best_name = track_key
            best_cfg = track_cfg

    return best_name, best_cfg
