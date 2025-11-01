import subprocess
import json
import re
import requests

class SocialScanner:
    def __init__(self):
        self.base_x = "https://nitter.net/search?f=tweets&q="
    
    def get_from_dexscreener_socials(self, pair: dict):
        """Extrae redes sociales si están en los metadatos del par DexScreener"""
        socials = []
        if not pair:
            return socials
        for field in ["info", "url", "socials"]:
            val = pair.get(field)
            if isinstance(val, str):
                socials.append(val)
            elif isinstance(val, list):
                socials += val
            elif isinstance(val, dict):
                socials += list(val.values())
        # filtra duplicados y no URLs
        return [s for s in socials if isinstance(s, str) and ("http" in s)]

    def twitter_mentions(self, keyword: str, limit: int = 20):
        """
        Usa snscrape (CLI) para contar tweets recientes del símbolo del token.
        Ejemplo: snscrape --jsonl twitter-search "USDC since:2024-10-01"
        """
        try:
            cmd = [
                "snscrape",
                "--jsonl",
                f"--max-results={limit}",
                f"twitter-search",
                f'"{keyword} since:2024-10-01"',
            ]
            output = subprocess.check_output(" ".join(cmd), shell=True, text=True, stderr=subprocess.DEVNULL)
            lines = output.splitlines()
            tweets = [json.loads(l) for l in lines if l.strip()]
            return len(tweets)
        except Exception:
            return 0

    def compute_hype_score(self, mentions: int) -> int:
        """
        Convierte cantidad de menciones recientes en puntaje (1–5)
        """
        if mentions == 0:
            return 2
        if mentions < 5:
            return 3
        if mentions < 20:
            return 4
        return 5
