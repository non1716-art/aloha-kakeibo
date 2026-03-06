
import os
import logging
from flask import Flask, request, abort
from linebot.v3 import WebhookHandler
from linebot.v3.exceptions import InvalidSignatureError
from linebot.v3.messaging import (
    Configuration,
    ApiClient,
    MessagingApi,
    ReplyMessageRequest,
    TextMessage,
)
from linebot.v3.webhooks import MessageEvent, ImageMessageContent

from services.line_handler import download_image
from services.ocr_handler import extract_receipt_data
from services.sheets_handler import append_to_sheet

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)

LINE_CHANNEL_SECRET = os.environ["LINE_CHANNEL_SECRET"]
LINE_CHANNEL_ACCESS_TOKEN = os.environ["LINE_CHANNEL_ACCESS_TOKEN"]

configuration = Configuration(access_token=LINE_CHANNEL_ACCESS_TOKEN)
handler = WebhookHandler(LINE_CHANNEL_SECRET)


@app.route("/webhook", methods=["POST"])
def webhook():
    signature = request.headers.get("X-Line-Signature", "")
    body = request.get_data(as_text=True)

    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        logger.warning("Invalid signature")
        abort(400)

    return "OK", 200


@handler.add(MessageEvent, message=ImageMessageContent)
def handle_image_message(event: MessageEvent):
    reply_token = event.reply_token
    message_id = event.message.id

    with ApiClient(configuration) as api_client:
        line_bot_api = MessagingApi(api_client)

        try:
            image_bytes = download_image(message_id, LINE_CHANNEL_ACCESS_TOKEN)
            receipt = extract_receipt_data(image_bytes)
            append_to_sheet(receipt)

            reply_text = (
                "領収書を記録しました\n\n"
                f"日付: {receipt.get('date', '不明')}\n"
                f"店名: {receipt.get('store', '不明')}\n"
                f"金額: {receipt.get('amount', '不明')}\n"
                f"内容: {receipt.get('description', '不明')}"
            )

        except Exception as e:
            logger.error(f"処理エラー: {e}", exc_info=True)
            reply_text = "領収書の処理中にエラーが発生しました。もう一度お試しください。"

        line_bot_api.reply_message(
            ReplyMessageRequest(
                reply_token=reply_token,
                messages=[TextMessage(text=reply_text)],
            )
        )


@app.route("/health", methods=["GET"])
def health():
    return {"status": "ok"}, 200


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    app.run(host="0.0.0.0", port=port)
