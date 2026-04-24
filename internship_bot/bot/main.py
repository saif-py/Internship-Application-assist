from __future__ import annotations

import argparse
import csv
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from .config_loader import (
    ConfigError,
    get_spreadsheet_id,
    load_yaml,
    merge_sources_config,
)
from .config import load_service_account_info, optional_env, resolve_repo_path
from .contacts import discover_contacts
from .models import AutofillPayload, JobListing, to_sheet_row
from .outreach import build_email, load_template
from .resume_tailor import create_tailored_resume
from .scoring import choose_role_track, is_target_listing, score_listing
from .sheet_client import ensure_worksheet, open_spreadsheet, upsert_rows
from .sources import fetch_all_listings
from .webhook_client import WebhookSyncError, sync_rows_via_webhook

LISTINGS_HEADERS = [
    "listing_id",
    "company",
    "role",
    "location",
    "employment_type",
    "team",
    "posted_at",
    "source",
    "fit_score",
    "score_reasons",
    "matched_keywords",
    "role_track",
    "apply_url",
    "tailored_resume_path",
    "quick_apply_payload_json",
    "autofill_name",
    "autofill_email",
    "autofill_phone",
    "autofill_linkedin",
    "autofill_portfolio",
    "autofill_location",
    "autofill_graduation",
    "autofill_work_auth",
    "autofill_relocate",
    "contact_emails",
    "status",
    "notes",
    "last_seen_utc",
]

CONTACT_HEADERS = [
    "contact_id",
    "listing_id",
    "company",
    "company_domain",
    "contact_name",
    "contact_title",
    "contact_email",
    "source",
    "confidence",
    "apply_url",
    "status",
    "notes",
    "last_seen_utc",
]

OUTREACH_HEADERS = [
    "outreach_id",
    "listing_id",
    "company",
    "role",
    "email_to",
    "email_subject",
    "email_body",
    "apply_url",
    "tailored_resume_path",
    "follow_up_on",
    "status",
    "reply_status",
    "notes",
    "last_seen_utc",
]


def parse_args(repo_root: Path) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Internship assistant pipeline")
    parser.add_argument(
        "--profile",
        default="internship_bot/config/profile.yaml",
        help="Path to candidate profile YAML",
    )
    parser.add_argument(
        "--sources",
        default="internship_bot/config/sources.yaml",
        help="Path to job sources YAML",
    )
    parser.add_argument(
        "--template",
        default="internship_bot/templates/outreach_email.txt",
        help="Path to outreach email template",
    )
    parser.add_argument(
        "--resume-output",
        default="internship_bot/generated_resumes",
        help="Output directory for tailored resume markdown files",
    )
    parser.add_argument(
        "--max-listings",
        type=int,
        default=150,
        help="Maximum listings to process after scoring",
    )
    parser.add_argument(
        "--min-score",
        type=int,
        default=-1,
        help="Minimum fit score; if not provided, value from profile targets.min_fit_score is used",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=25,
        help="HTTP timeout in seconds for source API calls",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Write CSVs to internship_bot/output instead of syncing to Google Sheets",
    )
    parser.add_argument(
        "--output-dir",
        default="internship_bot/output",
        help="Directory for dry-run CSV outputs",
    )
    return parser.parse_args()


def _write_csv(path: Path, headers: list[str], rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=headers)
        writer.writeheader()
        for row in rows:
            writer.writerow({key: row.get(key, "") for key in headers})


def _serialize_payload(candidate: dict[str, Any], resume_path: str, listing: JobListing) -> str:
    payload = {
        "full_name": candidate.get("full_name", ""),
        "email": candidate.get("email", ""),
        "phone": candidate.get("phone", ""),
        "linkedin": candidate.get("linkedin", ""),
        "portfolio": candidate.get("portfolio", ""),
        "location": candidate.get("current_location", ""),
        "graduation": candidate.get("graduation", ""),
        "work_authorization": candidate.get("work_authorization", ""),
        "willing_to_relocate": candidate.get("willing_to_relocate", ""),
        "target_company": listing.company,
        "target_role": listing.role,
        "apply_url": listing.apply_url,
        "tailored_resume_path": resume_path,
    }
    return json.dumps(payload, ensure_ascii=True)


def _as_relative(path: Path, repo_root: Path) -> str:
    try:
        return path.resolve().relative_to(repo_root.resolve()).as_posix()
    except ValueError:
        return path.as_posix()


def build_autofill_payload(candidate: dict[str, Any], resume_path: str) -> AutofillPayload:
    return AutofillPayload(
        full_name=str(candidate.get("full_name", "")),
        email=str(candidate.get("email", "")),
        phone=str(candidate.get("phone", "")),
        linkedin=str(candidate.get("linkedin", "")),
        portfolio=str(candidate.get("portfolio", "")),
        current_location=str(candidate.get("current_location", "")),
        graduation=str(candidate.get("graduation", "")),
        work_authorization=str(candidate.get("work_authorization", "")),
        willing_to_relocate=str(candidate.get("willing_to_relocate", "")),
        resume_path=resume_path,
    )


def _sync_with_webhook(
    webhook_url: str,
    webhook_token: str,
    sheet_names: dict[str, Any],
    listing_rows: list[dict[str, Any]],
    contact_rows: list[dict[str, Any]],
    outreach_rows: list[dict[str, Any]],
) -> None:
    operations = [
        {
            "sheet": str(sheet_names.get("listings", "internship_listings")),
            "keyField": "listing_id",
            "headers": LISTINGS_HEADERS,
            "preserveFields": ["status", "notes"],
            "rows": listing_rows,
        },
        {
            "sheet": str(sheet_names.get("contacts", "hiring_contacts")),
            "keyField": "contact_id",
            "headers": CONTACT_HEADERS,
            "preserveFields": ["status", "notes"],
            "rows": contact_rows,
        },
        {
            "sheet": str(sheet_names.get("outreach", "outreach_drafts")),
            "keyField": "outreach_id",
            "headers": OUTREACH_HEADERS,
            "preserveFields": ["status", "reply_status", "notes"],
            "rows": outreach_rows,
        },
    ]

    response = sync_rows_via_webhook(
        webhook_url=webhook_url,
        webhook_token=webhook_token,
        operations=operations,
        timeout=60,
    )
    results = response.get("results", [])

    summary_chunks = []
    for result in results:
        summary_chunks.append(
            f"{result.get('sheet', 'sheet')} u/a={result.get('updated', 0)}/{result.get('appended', 0)}"
        )

    summary = ", ".join(summary_chunks) if summary_chunks else "no operation summary returned"
    print(f"[info] webhook sheets sync complete | {summary}")


def main() -> int:
    repo_root = Path(__file__).resolve().parents[2]
    args = parse_args(repo_root)

    profile_path = resolve_repo_path(args.profile, repo_root)
    sources_path = resolve_repo_path(args.sources, repo_root)
    template_path = resolve_repo_path(args.template, repo_root)
    resume_output_root = resolve_repo_path(args.resume_output, repo_root)

    try:
        profile_cfg = load_yaml(profile_path)
        if not profile_cfg:
            raise ConfigError(f"Profile config is missing or empty: {profile_path}")

        sources_cfg = merge_sources_config(load_yaml(sources_path))
        candidate = profile_cfg.get("candidate", {})
        targets = profile_cfg.get("targets", {})
        role_tracks = profile_cfg.get("role_tracks", {})
        sheet_names = profile_cfg.get("sheet_names", {})

        starter_resume_raw = str(candidate.get("resume_path", "")).strip()
        if not starter_resume_raw:
            raise ConfigError("candidate.resume_path is required in profile.yaml")

        starter_resume_path = resolve_repo_path(starter_resume_raw, repo_root)
        template = load_template(template_path)

        min_score = args.min_score if args.min_score >= 0 else int(targets.get("min_fit_score", 55))

        listings = fetch_all_listings(sources_cfg, timeout=args.timeout)
        print(f"[info] fetched listings: {len(listings)}")

        scored: list[tuple[JobListing, dict[str, Any]]] = []
        for listing in listings:
            if not is_target_listing(listing, targets):
                continue

            score, reasons, matched_keywords = score_listing(listing, targets)
            if score < min_score:
                continue

            track_name, track_cfg = choose_role_track(listing, role_tracks)

            listing.fit_score = score
            listing.score_reasons = reasons
            listing.matched_keywords = matched_keywords
            listing.role_track = track_name

            scored.append((listing, track_cfg))

        scored.sort(key=lambda item: item[0].fit_score, reverse=True)
        scored = scored[: args.max_listings]
        print(f"[info] selected listings after filter: {len(scored)}")

        now_iso = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
        follow_up_date = (datetime.now(timezone.utc) + timedelta(days=5)).date().isoformat()
        run_output_dir = resume_output_root / datetime.now(timezone.utc).strftime("%Y%m%d")
        hunter_api_key = optional_env("HUNTER_API_KEY")

        listing_rows: list[dict[str, Any]] = []
        contact_rows: list[dict[str, Any]] = []
        outreach_rows: list[dict[str, Any]] = []

        for listing, track_cfg in scored:
            tailored_resume_path, summary_line, emphasis_line = create_tailored_resume(
                listing=listing,
                candidate=candidate,
                track_name=listing.role_track,
                track_cfg=track_cfg,
                starter_resume_path=starter_resume_path,
                output_dir=run_output_dir,
            )
            tailored_resume_rel = _as_relative(tailored_resume_path, repo_root)

            contacts = discover_contacts(listing, hunter_api_key=hunter_api_key)
            contact_emails = "; ".join(contact.contact_email for contact in contacts)
            primary_contact = contacts[0] if contacts else None

            email_to, email_subject, email_body = build_email(
                template=template,
                listing=listing,
                candidate=candidate,
                primary_contact=primary_contact,
                role_track=listing.role_track,
                summary_line=summary_line,
                emphasis_line=emphasis_line,
                resume_path=tailored_resume_rel,
            )

            autofill = build_autofill_payload(candidate, tailored_resume_rel)
            autofill_row = to_sheet_row(autofill)

            listing_row: dict[str, Any] = {
                "listing_id": listing.listing_id,
                "company": listing.company,
                "role": listing.role,
                "location": listing.location,
                "employment_type": listing.employment_type,
                "team": listing.team,
                "posted_at": listing.posted_at,
                "source": listing.source,
                "fit_score": listing.fit_score,
                "score_reasons": listing.score_reasons,
                "matched_keywords": ", ".join(listing.matched_keywords),
                "role_track": listing.role_track,
                "apply_url": listing.apply_url,
                "tailored_resume_path": tailored_resume_rel,
                "quick_apply_payload_json": _serialize_payload(candidate, tailored_resume_rel, listing),
                "contact_emails": contact_emails,
                "status": "",
                "notes": "",
                "last_seen_utc": now_iso,
            }
            listing_row.update(autofill_row)
            listing_rows.append(listing_row)

            for contact in contacts:
                contact_rows.append(
                    {
                        "contact_id": f"{listing.listing_id}|{contact.contact_email.lower()}",
                        "listing_id": listing.listing_id,
                        "company": listing.company,
                        "company_domain": contact.company_domain,
                        "contact_name": contact.contact_name,
                        "contact_title": contact.contact_title,
                        "contact_email": contact.contact_email,
                        "source": contact.source,
                        "confidence": contact.confidence,
                        "apply_url": listing.apply_url,
                        "status": "",
                        "notes": "",
                        "last_seen_utc": now_iso,
                    }
                )

            outreach_rows.append(
                {
                    "outreach_id": f"outreach:{listing.listing_id}",
                    "listing_id": listing.listing_id,
                    "company": listing.company,
                    "role": listing.role,
                    "email_to": email_to,
                    "email_subject": email_subject,
                    "email_body": email_body,
                    "apply_url": listing.apply_url,
                    "tailored_resume_path": tailored_resume_rel,
                    "follow_up_on": follow_up_date,
                    "status": "draft",
                    "reply_status": "",
                    "notes": "",
                    "last_seen_utc": now_iso,
                }
            )

        if args.dry_run:
            output_dir = resolve_repo_path(args.output_dir, repo_root)
            _write_csv(output_dir / "listings.csv", LISTINGS_HEADERS, listing_rows)
            _write_csv(output_dir / "contacts.csv", CONTACT_HEADERS, contact_rows)
            _write_csv(output_dir / "outreach.csv", OUTREACH_HEADERS, outreach_rows)
            print(f"[info] dry-run files written to: {output_dir}")
            return 0

        webhook_url = optional_env("SHEETS_WEBHOOK_URL")
        webhook_token = optional_env("SHEETS_WEBHOOK_TOKEN")

        if webhook_url:
            _sync_with_webhook(
                webhook_url=webhook_url,
                webhook_token=webhook_token,
                sheet_names=sheet_names,
                listing_rows=listing_rows,
                contact_rows=contact_rows,
                outreach_rows=outreach_rows,
            )
            return 0

        service_account_info = load_service_account_info()
        spreadsheet_id = get_spreadsheet_id(profile_cfg)
        spreadsheet = open_spreadsheet(service_account_info, spreadsheet_id)

        listings_sheet = ensure_worksheet(
            spreadsheet,
            str(sheet_names.get("listings", "internship_listings")),
            LISTINGS_HEADERS,
        )
        contacts_sheet = ensure_worksheet(
            spreadsheet,
            str(sheet_names.get("contacts", "hiring_contacts")),
            CONTACT_HEADERS,
        )
        outreach_sheet = ensure_worksheet(
            spreadsheet,
            str(sheet_names.get("outreach", "outreach_drafts")),
            OUTREACH_HEADERS,
        )

        list_updated, list_appended = upsert_rows(
            listings_sheet,
            listing_rows,
            key_field="listing_id",
            headers=LISTINGS_HEADERS,
            preserve_fields=["status", "notes"],
        )
        contact_updated, contact_appended = upsert_rows(
            contacts_sheet,
            contact_rows,
            key_field="contact_id",
            headers=CONTACT_HEADERS,
            preserve_fields=["status", "notes"],
        )
        outreach_updated, outreach_appended = upsert_rows(
            outreach_sheet,
            outreach_rows,
            key_field="outreach_id",
            headers=OUTREACH_HEADERS,
            preserve_fields=["status", "reply_status", "notes"],
        )

        print(
            "[info] sheets sync complete | "
            f"listings u/a={list_updated}/{list_appended}, "
            f"contacts u/a={contact_updated}/{contact_appended}, "
            f"outreach u/a={outreach_updated}/{outreach_appended}"
        )
        return 0

    except (ConfigError, FileNotFoundError, WebhookSyncError) as exc:
        print(f"[error] {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
