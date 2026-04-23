from __future__ import annotations

from typing import Iterable
from urllib.parse import urlparse

import requests

from .models import ContactRecord, JobListing

GENERIC_EMAIL_PREFIXES = [
    "careers",
    "jobs",
    "hr",
    "recruiting",
    "talent",
    "people",
]

TITLE_PRIORITY_KEYWORDS = [
    "talent acquisition",
    "recruiter",
    "hiring",
    "people",
    "human resources",
    "founder",
    "ceo",
    "head",
]


def _root_domain(value: str) -> str:
    domain = (value or "").strip().lower()
    if not domain:
        return ""

    if "://" in domain:
        domain = urlparse(domain).netloc.lower()

    domain = domain.split(":")[0]
    if domain.startswith("www."):
        domain = domain[4:]

    chunks = [part for part in domain.split(".") if part]
    if len(chunks) >= 2:
        return ".".join(chunks[-2:])
    return domain


def infer_domain(listing: JobListing) -> str:
    if listing.company_domain:
        return _root_domain(listing.company_domain)

    netloc = _root_domain(listing.apply_url)
    if netloc.endswith("greenhouse.io") or netloc.endswith("lever.co"):
        return ""

    return netloc


def _generic_contacts(company: str, domain: str) -> list[ContactRecord]:
    if not domain:
        return []

    return [
        ContactRecord(
            company=company,
            company_domain=domain,
            contact_email=f"{prefix}@{domain}",
            contact_name="",
            contact_title="Recruiting Team",
            source="pattern",
            confidence=35,
        )
        for prefix in GENERIC_EMAIL_PREFIXES
    ]


def _score_title(title: str) -> int:
    text = (title or "").lower()
    score = 0
    for idx, keyword in enumerate(TITLE_PRIORITY_KEYWORDS):
        if keyword in text:
            score += max(10 - idx, 2)
    return score


def _hunter_contacts(company: str, domain: str, hunter_api_key: str, timeout: int = 20) -> list[ContactRecord]:
    if not hunter_api_key or not domain:
        return []

    url = "https://api.hunter.io/v2/domain-search"
    params = {
        "domain": domain,
        "api_key": hunter_api_key,
        "limit": 12,
    }

    response = requests.get(url, params=params, timeout=timeout)
    response.raise_for_status()

    payload = response.json() if response.content else {}
    emails = payload.get("data", {}).get("emails", []) if isinstance(payload, dict) else []

    contacts: list[ContactRecord] = []
    for item in emails:
        if not isinstance(item, dict):
            continue

        email = str(item.get("value", "")).strip().lower()
        if not email:
            continue

        first_name = str(item.get("first_name", "")).strip()
        last_name = str(item.get("last_name", "")).strip()
        full_name = " ".join(part for part in [first_name, last_name] if part)
        title = str(item.get("position", "")).strip()
        base_confidence = int(item.get("confidence", 0) or 0)
        confidence = min(100, base_confidence + _score_title(title))

        contacts.append(
            ContactRecord(
                company=company,
                company_domain=domain,
                contact_email=email,
                contact_name=full_name,
                contact_title=title,
                source="hunter",
                confidence=confidence,
            )
        )

    return contacts


def _dedupe_contacts(contacts: Iterable[ContactRecord]) -> list[ContactRecord]:
    deduped: dict[str, ContactRecord] = {}
    for contact in contacts:
        key = contact.contact_email.lower()
        existing = deduped.get(key)
        if not existing or contact.confidence > existing.confidence:
            deduped[key] = contact

    ordered = sorted(deduped.values(), key=lambda item: item.confidence, reverse=True)
    return ordered


def discover_contacts(listing: JobListing, hunter_api_key: str = "", max_contacts: int = 6) -> list[ContactRecord]:
    domain = infer_domain(listing)
    if not domain:
        return []

    contacts = []

    try:
        contacts.extend(_hunter_contacts(listing.company, domain, hunter_api_key=hunter_api_key))
    except requests.RequestException as exc:
        print(f"[warn] hunter lookup failed for {domain}: {exc}")

    contacts.extend(_generic_contacts(listing.company, domain))

    deduped = _dedupe_contacts(contacts)
    return deduped[:max_contacts]
