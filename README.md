# Internship Application Assistant

This is a standalone repository for your internship automation workflow.

It is built for manual-safe execution:

1. Finds internship listings from configured company ATS sources
2. Scores listings for your target lanes (non-tech, product, AI-adjacent)
3. Maintains 3 Google Sheets tabs (listings, contacts, outreach drafts)
4. Generates company-role tailored resume drafts from your starter resume
5. Gives direct apply links and autofill-ready candidate payload fields

## Project Structure

- `internship_bot/` - core application code and configs
- `.github/workflows/internship-bot.yml` - scheduled GitHub Actions run

## Quick Start

```bash
pip install -r requirements.txt
python internship_bot/run.py --dry-run
```

Then update:

- `internship_bot/config/profile.yaml`
- `internship_bot/config/sources.yaml`

For cloud runs, add GitHub secrets documented in `internship_bot/README.md`.

## Push As New GitHub Repository

```bash
git init
git add .
git commit -m "Initial commit: internship application assistant"
git branch -M main
git remote add origin <your-new-repo-url>
git push -u origin main
```
