
import logging
import os
import re
from google.cloud import vision

logger = logging.getLogger(__name__)

_AMOUNT_PATTERNS = [
    r"(?:合計|小計|お会計|総額|金額|請求額)[^\d￥¥]*[￥¥]?\s*([\d,]+)",
    r"[￥¥]\s*([\d,]+)",
    r"([\d,]+)\s*円",
]

_DATE_PATTERNS = [
    r"(\d{4}[年/\-]\d{1,2}[月/\-]\d{1,2}日?)",
    r"(\d{2}[年/\-]\d{1,2}[月/\-]\d{1,2}日?)",
    r"R(\d+)[年/]\s*(\d{1,2})[月/]\s*(\d{1,2})日?",
]


def _setup_credentials() -> None:
    creds_json = os.environ.get("GOOGLE_CREDENTIALS_JSON")
    if creds_json and not os.environ.get("GOOGLE_APPLICATION_CREDENTIALS"):
        creds_path = "/tmp/gcp_credentials.json"
        with open(creds_path, "w") as f:
            f.write(creds_json)
        os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = creds_path


def extract_receipt_data(image_bytes: bytes) -> dict:
    _setup_credentials()

    client = vision.ImageAnnotatorClient()
    image = vision.Image(content=image_bytes)
    response = client.text_detection(image=image)

    if response.error.message:
        raise RuntimeError(f"Vision API error: {response.error.message}")

    full_text = response.full_text_annotation.text if response.full_text_annotation else ""
    logger.info("OCR raw text: %s", full_text[:300])

    return {
        "date": _extract_date(full_text),
        "store": _extract_store(full_text, response.text_annotations),
        "amount": _extract_amount(full_text),
        "description": _extract_description(full_text),
        "raw_text": full_text,
    }


def _extract_date(text: str) -> str:
    for pattern in _DATE_PATTERNS:
        match = re.search(pattern, text)
        if match:
            matched = match.group(0)
            reiwa = re.match(r"R(\d+)[年/]\s*(\d{1,2})[月/]\s*(\d{1,2})", matched)
            if reiwa:
                year = 2018 + int(reiwa.group(1))
                return f"{year}/{reiwa.group(2)}/{reiwa.group(3)}"
            normalized = re.sub(r"[年月]", "/", matched).rstrip("日").strip()
            return normalized
    return ""


def _extract_store(text: str, annotations) -> str:
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    if not lines:
        return ""
    candidates = lines[:3]
    return max(candidates, key=len)


def _extract_amount(text: str) -> str:
    for pattern in _AMOUNT_PATTERNS:
        match = re.search(pattern, text)
        if match:
            amount_str = match.group(1).replace(",", "")
            return f"¥{int(amount_str):,}"
    return ""


def _extract_description(text: str) -> str:
    lines = text.splitlines()
    items = []
    skip_keywords = {"合計", "小計", "税", "消費税", "お釣", "お預", "領収", "レシート", "TEL", "FAX", "〒"}

    for line in lines:
        line = line.strip()
        if not line:
            continue
        if any(kw in line for kw in skip_keywords):
            continue
        if re.search(r"[￥¥]\s*[\d,]+", line) or re.match(r"^[\d,]+$", line):
            continue
        if re.search(r"\d{4}[年/\-]", line):
            continue
        if len(line) > 1:
            items.append(line)
        if len(items) >= 3:
            break

    return " / ".join(items) if items else ""
