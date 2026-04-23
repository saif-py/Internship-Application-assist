from __future__ import annotations

from typing import Iterable

import gspread
from google.oauth2.service_account import Credentials

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]


def open_spreadsheet(service_account_info: dict, spreadsheet_id: str) -> gspread.Spreadsheet:
    creds = Credentials.from_service_account_info(service_account_info, scopes=SCOPES)
    client = gspread.authorize(creds)
    return client.open_by_key(spreadsheet_id)


def ensure_worksheet(
    spreadsheet: gspread.Spreadsheet,
    title: str,
    headers: list[str],
    rows: int = 2000,
    cols: int = 40,
) -> gspread.Worksheet:
    try:
        worksheet = spreadsheet.worksheet(title)
    except gspread.WorksheetNotFound:
        worksheet = spreadsheet.add_worksheet(title=title, rows=rows, cols=max(cols, len(headers) + 5))

    current_headers = worksheet.row_values(1)
    if current_headers != headers:
        worksheet.update("A1", [headers], value_input_option="RAW")

    return worksheet


def _sanitize_cell(value: object) -> str:
    if value is None:
        return ""
    return str(value)


def upsert_rows(
    worksheet: gspread.Worksheet,
    rows: Iterable[dict[str, object]],
    key_field: str,
    headers: list[str],
    preserve_fields: list[str] | None = None,
) -> tuple[int, int]:
    preserve_fields = preserve_fields or []
    incoming_rows = list(rows)
    if not incoming_rows:
        return 0, 0

    existing_records = worksheet.get_all_records(default_blank="")
    existing_index: dict[str, int] = {}
    existing_by_key: dict[str, dict] = {}

    for index, record in enumerate(existing_records, start=2):
        key = str(record.get(key_field, "")).strip()
        if key:
            existing_index[key] = index
            existing_by_key[key] = record

    updated_count = 0
    appended_count = 0

    for row in incoming_rows:
        key = str(row.get(key_field, "")).strip()
        merged = {header: row.get(header, "") for header in headers}

        if key in existing_by_key:
            previous = existing_by_key[key]
            for field in preserve_fields:
                old_val = str(previous.get(field, "")).strip()
                new_val = str(merged.get(field, "")).strip()
                if old_val and not new_val:
                    merged[field] = old_val

            values = [[_sanitize_cell(merged.get(header, "")) for header in headers]]
            worksheet.update(f"A{existing_index[key]}", values, value_input_option="RAW")
            updated_count += 1
            continue

        values = [_sanitize_cell(merged.get(header, "")) for header in headers]
        worksheet.append_row(values, value_input_option="RAW")
        appended_count += 1

    return updated_count, appended_count
