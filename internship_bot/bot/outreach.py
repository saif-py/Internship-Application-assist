from __future__ import annotations

from pathlib import Path
from typing import Any

from .models import ContactRecord, JobListing


class _SafeDict(dict):
    def __missing__(self, key: str) -> str:
        return ""


def load_template(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def build_email(
    template: str,
    listing: JobListing,
    candidate: dict[str, Any],
    primary_contact: ContactRecord | None,
    role_track: str,
    summary_line: str,
    emphasis_line: str,
    resume_path: str,
) -> tuple[str, str, str]:
    to_email = primary_contact.contact_email if primary_contact else ""
    contact_name = (
        primary_contact.contact_name
        if primary_contact and primary_contact.contact_name
        else "Hiring Team"
    )

    context = _SafeDict(
        {
            "hiring_contact_name": contact_name,
            "candidate_name": candidate.get("full_name", ""),
            "candidate_email": candidate.get("email", ""),
            "candidate_phone": candidate.get("phone", ""),
            "candidate_linkedin": candidate.get("linkedin", ""),
            "candidate_headline": candidate.get("headline", ""),
            "company": listing.company,
            "role": listing.role,
            "apply_url": listing.apply_url,
            "role_track": role_track,
            "summary_line": summary_line,
            "emphasis_line": emphasis_line,
            "resume_path": resume_path,
        }
    )

    subject = f"Application for {listing.role} Internship - {candidate.get('full_name', '')}".strip()
    body = template.format_map(context)
    return to_email, subject, body
