from __future__ import annotations

import re
from collections import Counter
from pathlib import Path
from typing import Any

from .models import JobListing

STOPWORDS = {
    "about",
    "after",
    "also",
    "been",
    "being",
    "company",
    "experience",
    "from",
    "have",
    "internship",
    "into",
    "must",
    "that",
    "their",
    "this",
    "with",
    "will",
    "work",
    "your",
}


def _slugify(text: str) -> str:
    clean = re.sub(r"[^a-zA-Z0-9]+", "-", text.lower())
    return clean.strip("-") or "target-role"


def _extract_keywords(text: str, limit: int = 10) -> list[str]:
    words = re.findall(r"[a-zA-Z]{4,}", (text or "").lower())
    counter = Counter(word for word in words if word not in STOPWORDS)
    return [token for token, _ in counter.most_common(limit)]


def create_tailored_resume(
    listing: JobListing,
    candidate: dict[str, Any],
    track_name: str,
    track_cfg: dict[str, Any],
    starter_resume_path: Path,
    output_dir: Path,
) -> tuple[Path, str, str]:
    if not starter_resume_path.exists():
        raise FileNotFoundError(f"Starter resume not found: {starter_resume_path}")

    starter_text = starter_resume_path.read_text(encoding="utf-8")

    summary_template = track_cfg.get(
        "summary_template",
        "{candidate_name} is interested in {role} at {company} with strong business, execution, and analytics skills.",
    )
    summary_line = summary_template.format(
        candidate_name=candidate.get("full_name", ""),
        role=listing.role,
        company=listing.company,
    )

    emphasis_skills = track_cfg.get("emphasis_skills", [])
    emphasis_line = ", ".join(emphasis_skills[:8])

    extracted_keywords = _extract_keywords(f"{listing.role} {listing.description}")
    keywords_line = ", ".join(extracted_keywords)

    preface = [
        "# Tailored Resume Context",
        f"Target Company: {listing.company}",
        f"Target Role: {listing.role}",
        f"Role Track: {track_name}",
        "",
        "## Customized Summary",
        summary_line,
        "",
        "## JD Keywords To Weave Into Bullets",
        f"- {keywords_line}" if keywords_line else "- Add role-specific verbs and metrics from the JD.",
        "",
        "## Skill Emphasis",
        f"- {emphasis_line}" if emphasis_line else "- Product thinking, stakeholder management, analytics, communication",
        "",
        "---",
        "",
    ]

    file_name = f"{_slugify(listing.company)}__{_slugify(listing.role)}__{_slugify(listing.listing_id)}.md"
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / file_name

    output_text = "\n".join(preface) + starter_text
    output_path.write_text(output_text, encoding="utf-8")

    return output_path, summary_line, emphasis_line
