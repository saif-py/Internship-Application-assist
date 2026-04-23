# Internship Application Assistant (GitHub + Google Sheets)

This module runs a cloud-scheduled internship pipeline with manual-safe execution:

1. Fetches internship listings from configured ATS sources (Greenhouse, Lever)
2. Scores and filters listings for non-tech, product, and AI-adjacent roles
3. Maintains 3 Google Sheets tabs:
   - `internship_listings`
   - `hiring_contacts`
   - `outreach_drafts`
4. Generates company-role tailored resume drafts from your starter resume
5. Produces direct apply links + autofill-ready data for manual final submit

This is designed for your workflow: you stay manually involved for application submit and email sending.

## Folder Overview

- `internship_bot/run.py`: main entrypoint
- `internship_bot/bot/main.py`: pipeline orchestration
- `internship_bot/config/profile.yaml`: your candidate profile + targets
- `internship_bot/config/sources.yaml`: company source endpoints
- `internship_bot/templates/outreach_email.txt`: outreach draft template
- `.github/workflows/internship-bot.yml`: scheduled cloud run

## Setup

1. Create a Google Spreadsheet and note the spreadsheet ID.
2. Create a Google service account JSON key.
3. Share the spreadsheet with the service account email as Editor.
4. Fill your details in `internship_bot/config/profile.yaml`.
5. Add target companies in `internship_bot/config/sources.yaml`.

## GitHub Secrets

Add these repository secrets:

- `GOOGLE_SPREADSHEET_ID`
- `GOOGLE_SHEETS_CREDENTIALS_JSON`
- `HUNTER_API_KEY` (optional for stronger contact discovery)
- `CANDIDATE_PROFILE_YAML` (optional override for profile file)
- `JOB_SOURCES_YAML` (optional override for sources file)

## Local Dry Run

```bash
pip install -r internship_bot/requirements.txt
python internship_bot/run.py --dry-run
```

Dry-run writes CSVs to `internship_bot/output/`.

## Scheduled Cloud Run

After pushing to GitHub:

1. Open Actions tab
2. Run `Internship Assistant Sync` manually once
3. Confirm the three sheets are populated
4. Scheduled sync runs every 8 hours

## Sheet Columns You Will Use Most

`internship_listings` contains:
- apply links
- fit score
- role track
- tailored resume path
- quick apply payload JSON
- autofill fields (name, email, phone, LinkedIn, etc.)

`hiring_contacts` contains:
- recruiter/team email suggestions
- confidence score

`outreach_drafts` contains:
- draft subject/body
- follow-up date

## Important Notes

- Keep final submit manual to avoid account restrictions and improve quality.
- Some sources may fail occasionally; the bot skips failed sources and continues.
- Contact emails are best-effort suggestions and should be verified before use.
