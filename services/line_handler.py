import requests

def download_image(message_id: str, channel_access_token: str) -> bytes:
    url = f"https://api-data.line.me/v2/bot/message/{message_id}/content"

    headers = {
        "Authorization": f"Bearer {channel_access_token}"
    }

    response = requests.get(url, headers=headers, timeout=30)
    response.raise_for_status()

    return response.content
