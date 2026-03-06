import logging
import os
from datetime import datetime

import gspread
from google.oauth2.service_account import Credentials

logger = logging.getLogger(__name__)

_SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive.file",
]

_HEADERS = ["記録日時", "日付", "店名", "金額", "内容", "OCR全文"]


def _get_client() -> gspread.Client:
    creds_json = os.environ.get("GOOGLE_CREDENTIALS_JSON")
    if not creds_json:
        raise EnvironmentError("GOOGLE_CREDENTIALS_JSON が設定されていません")

    import json
    info = json.loads(creds_json)
    creds = Credentials.from_service_account_info(info, scopes=_SCOPES)
    return gspread.authorize(creds)


def _get_or_create_sheet(client: gspread.Client, spreadsheet_id: str) -> gspread.Worksheet:
    spreadsheet = client.open_by_key(spreadsheet_id)

    try:
        sheet = spreadsheet.worksheet("領収書")
    except gspread.WorksheetNotFound:
        sheet = spreadsheet.add_worksheet(title="領収書", rows=1000, cols=10)

    if sheet.row_count == 0 or sheet.cell(1, 1).value != _HEADERS[0]:
        sheet.insert_row(_HEADERS, index=1)

    return sheet


def append_to_sheet(receipt: dict) -> None:
    spreadsheet_id = os.environ.get("SPREADSHEET_ID")
    if not spreadsheet_id:
        raise EnvironmentError("SPREADSHEET_ID が設定されていません")

    client = _get_client()
    sheet = _get_or_create_sheet(client, spreadsheet_id)

    now = datetime.now().strftime("%Y/%m/%d %H:%M:%S")
    row = [
        now,
        receipt.get("date", ""),
        receipt.get("store", ""),
        receipt.get("amount", ""),
        receipt.get("description", ""),
        receipt.get("raw_text", "")[:500],
    ]

    sheet.append_row(row, value_input_option="USER_ENTERED")
    logger.info("スプレッドシートに追記: %s", row[:5])
