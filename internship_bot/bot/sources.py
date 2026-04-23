from __future__ import annotations

import html
import re
from datetime import datetime, timezone
from typing import Any

import requests

from .models import JobListing

REQUEST_HEADERS = {
    "User-Agent": "internship-assistant/1.0 (+github-actions)",
}

TAG_PATTERN = re.compile(r"<[^>]+>")


def _strip_html(raw_text: str) -> str:
    text = TAG_PATTERN.sub(" ", raw_text or "")
    text = html.unescape(text)
    return " ".join(text.split())


def _ms_to_iso8601(value: Any) -> str:
    if value in (None, ""):
        return ""

    try:
        millis = int(value)
    except (TypeError, ValueError):
        return str(value)

    dt = datetime.fromtimestamp(millis / 1000, tz=timezone.utc)
    return dt.isoformat()


def fetch_greenhouse(source_cfg: dict[str, Any], timeout: int = 25) -> list[JobListing]:
    board_token = str(source_cfg.get("board_token", "")).strip()
    if not board_token:
        return []

    company = str(source_cfg.get("company", board_token.replace("-", " ").title())).strip()
    company_domain = str(source_cfg.get("domain", "")).strip().lower()

    url = f"https://boards-api.greenhouse.io/v1/boards/{board_token}/jobs?content=true"
    response = requests.get(url, headers=REQUEST_HEADERS, timeout=timeout)
    response.raise_for_status()

    payload = response.json() if response.content else {}
    jobs = payload.get("jobs", []) if isinstance(payload, dict) else []

    listings: list[JobListing] = []
    for item in jobs:
        if not isinstance(item, dict):
            continue

        job_id = str(item.get("id", "")).strip()
        role = str(item.get("title", "")).strip()
        if not role:
            continue

        location_obj = item.get("location", {}) or {}
        location = str(location_obj.get("name", "") or source_cfg.get("default_location", "Unknown")).strip()
        apply_url = str(item.get("absolute_url", "")).strip()
        posted_at = str(item.get("updated_at", "") or item.get("created_at", "")).strip()
        description = _strip_html(str(item.get("content", "")))

        listings.append(
            JobListing(
                listing_id=f"greenhouse:{board_token}:{job_id}",
                company=company,
                role=role,
                location=location or "Unknown",
                source=f"greenhouse:{board_token}",
                apply_url=apply_url,
                posted_at=posted_at,
                description=description,
                company_domain=company_domain,
                employment_type="",
                team="",
            )
        )

    return listings


def fetch_lever(source_cfg: dict[str, Any], timeout: int = 25) -> list[JobListing]:
    company_slug = str(source_cfg.get("company_slug", "")).strip()
    if not company_slug:
        return []

    company = str(source_cfg.get("company", company_slug.replace("-", " ").title())).strip()
    company_domain = str(source_cfg.get("domain", "")).strip().lower()

    url = f"https://api.lever.co/v0/postings/{company_slug}?mode=json"
    response = requests.get(url, headers=REQUEST_HEADERS, timeout=timeout)
    response.raise_for_status()

    jobs = response.json() if response.content else []
    if not isinstance(jobs, list):
        return []

    listings: list[JobListing] = []
    for item in jobs:
        if not isinstance(item, dict):
            continue

        state = str(item.get("state", "published")).lower()
        if state not in {"published", "active"}:
            continue

        role = str(item.get("text", "")).strip()
        if not role:
            continue

        categories = item.get("categories", {}) or {}
        location = str(categories.get("location", "") or source_cfg.get("default_location", "Unknown")).strip()
        team = str(categories.get("team", "")).strip()
        commitment = str(categories.get("commitment", "")).strip()

        listing_id = str(item.get("id", "")).strip() or role.lower().replace(" ", "-")
        apply_url = str(item.get("hostedUrl", "") or item.get("applyUrl", "")).strip()
        posted_at = _ms_to_iso8601(item.get("createdAt"))
        description = _strip_html(str(item.get("descriptionPlain", "") or item.get("description", "")))

        listings.append(
            JobListing(
                listing_id=f"lever:{company_slug}:{listing_id}",
                company=company,
                role=role,
                location=location or "Unknown",
                source=f"lever:{company_slug}",
                apply_url=apply_url,
                posted_at=posted_at,
                description=description,
                company_domain=company_domain,
                employment_type=commitment,
                team=team,
            )
        )

    return listings


def fetch_all_listings(sources_cfg: dict[str, Any], timeout: int = 25) -> list[JobListing]:
    all_listings: list[JobListing] = []

    for source in sources_cfg.get("greenhouse", []):
        try:
            all_listings.extend(fetch_greenhouse(source, timeout=timeout))
        except requests.RequestException as exc:
            print(f"[warn] greenhouse source failed ({source}): {exc}")

    for source in sources_cfg.get("lever", []):
        try:
            all_listings.extend(fetch_lever(source, timeout=timeout))
        except requests.RequestException as exc:
            print(f"[warn] lever source failed ({source}): {exc}")

    # De-duplicate by listing id while keeping first seen item.
    deduped: dict[str, JobListing] = {}
    for listing in all_listings:
        deduped.setdefault(listing.listing_id, listing)

    return list(deduped.values())
