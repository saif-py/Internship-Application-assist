# Apps Script Webhook Setup (No Service Account JSON)

Use this if you want GitHub Actions to write to Google Sheets without storing a Google service-account key.

## 1) Prepare your target spreadsheet

1. Open your Google Sheet.
2. Create (or keep) these tabs. Names can be changed later in `profile.yaml`.
   - `internship_listings`
   - `hiring_contacts`
   - `outreach_drafts`

## 2) Add Apps Script code

1. In the same Google Sheet, click **Extensions -> Apps Script**.
2. Replace the default script with code from `internship_bot/apps_script/Code.gs`.
3. Click **Save**.

## 3) Set webhook token in Apps Script

1. In Apps Script, open **Project Settings**.
2. Under **Script properties**, add:
   - Key: `SHEETS_WEBHOOK_TOKEN`
   - Value: any long random secret string

Use a strong value (for example 32+ chars).

## 4) Deploy web app

1. Click **Deploy -> New deployment**.
2. Choose type: **Web app**.
3. Execute as: **Me**.
4. Who has access: **Anyone**.
5. Click **Deploy** and authorize.
6. Copy the **Web app URL**.

If you update script code later, redeploy a new version and keep using the newest web app URL.

## 5) Add GitHub secrets

In GitHub repo settings -> **Secrets and variables -> Actions**, add:

- `SHEETS_WEBHOOK_URL` = your Apps Script web app URL
- `SHEETS_WEBHOOK_TOKEN` = same token you set in Script properties

Optional bot secrets:

- `HUNTER_API_KEY`
- `CANDIDATE_PROFILE_YAML`
- `JOB_SOURCES_YAML`

With webhook mode, you can skip `GOOGLE_SHEETS_CREDENTIALS_JSON`.

## 6) Run workflow

1. Go to **Actions**.
2. Run **Internship Assistant Sync** manually once.
3. Confirm rows appear in the 3 tabs.

## Troubleshooting

- Error says invalid token: token in GitHub and Apps Script property do not match.
- No rows written: check web app deployment access is set to Anyone.
- Still using old deployment: redeploy and update `SHEETS_WEBHOOK_URL` secret.
