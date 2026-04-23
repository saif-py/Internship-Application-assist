from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List


@dataclass
class JobListing:
    listing_id: str
    company: str
    role: str
    location: str
    source: str
    apply_url: str
    posted_at: str = ""
    description: str = ""
    company_domain: str = ""
    employment_type: str = ""
    team: str = ""
    fit_score: int = 0
    score_reasons: str = ""
    role_track: str = ""
    matched_keywords: List[str] = field(default_factory=list)


@dataclass
class ContactRecord:
    company: str
    company_domain: str
    contact_name: str
    contact_title: str
    contact_email: str
    source: str
    confidence: int


@dataclass
class AutofillPayload:
    full_name: str
    email: str
    phone: str
    linkedin: str
    portfolio: str
    current_location: str
    graduation: str
    work_authorization: str
    willing_to_relocate: str
    resume_path: str


def to_sheet_row(payload: AutofillPayload) -> Dict[str, str]:
    return {
        "autofill_name": payload.full_name,
        "autofill_email": payload.email,
        "autofill_phone": payload.phone,
        "autofill_linkedin": payload.linkedin,
        "autofill_portfolio": payload.portfolio,
        "autofill_location": payload.current_location,
        "autofill_graduation": payload.graduation,
        "autofill_work_auth": payload.work_authorization,
        "autofill_relocate": payload.willing_to_relocate,
        "tailored_resume_path": payload.resume_path,
    }
