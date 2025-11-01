import requests
from typing import Optional

class TelegramBot:
    def __init__(self, bot_token: str):
        self.base = f"https://api.telegram.org/bot{bot_token}"

    def send_message(self, chat_id: str, text: str, parse_mode: Optional[str] = "HTML") -> bool:
        try:
            r = requests.post(f"{self.base}/sendMessage", json={
                "chat_id": chat_id,
                "text": text,
                "parse_mode": parse_mode,
                "disable_web_page_preview": True
            }, timeout=20)
            return r.status_code == 200
        except Exception:
            return False
