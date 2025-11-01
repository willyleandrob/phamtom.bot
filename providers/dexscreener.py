import requests
import re

_BASE = "https://api.dexscreener.com/latest/dex"

class DexScreener:
    @staticmethod
    def parse_pair_from_url(url):
        m = re.search(r"dexscreener\.com/[^/]+/([0-9a-fA-Fx]{42,})", url)
        return m.group(1) if m else None

    @staticmethod
    def get_pair_by_address(chain: str, pair_address: str):
        # Ej: /pairs/ethereum/0xPAR
        r = requests.get(f"{_BASE}/pairs/{chain}/{pair_address}", timeout=15)
        if r.status_code != 200:
            return None
        data = r.json()
        pairs = data.get("pairs") or []
        return pairs[0] if pairs else None

    @staticmethod
    def get_token_pairs(chain: str, token_address: str):
        # Busca todos los pares donde aparece el token y se queda con el de mayor liquidez
        r = requests.get(f"{_BASE}/search?q={token_address}", timeout=15)
        if r.status_code != 200:
            return None
        data = r.json()
        pairs = data.get("pairs") or []
        if not pairs:
            return None
        if chain:
            pairs = [p for p in pairs if (p.get("chainId") or "").lower() == chain.lower()]
        if not pairs:
            return None
        pairs.sort(key=lambda p: float((p.get("liquidity", {}) or {}).get("usd", 0) or 0), reverse=True)
        return pairs[0]
        def get_new_tokens(self, chain: str, max_age_minutes: int = 180, limit: int = 200) -> List[Dict[str, Any]]:
        """
        Busca pares recientemente creados en una chain usando:
        GET /latest/dex/pairs/{chain}
        Filtra por edad del par (pairCreatedAt) en los últimos 'max_age_minutes'.
        Devuelve entradas normalizadas con: tokenAddress, symbol, liquidity.usd, url, socials.
        """
        import time
        url = f"{self.BASE}/pairs/{chain}"
        r = requests.get(url, timeout=25)
        if r.status_code != 200:
            return []

        now_ms = int(time.time() * 1000)
        max_age_ms = max_age_minutes * 60 * 1000
        pairs = (r.json() or {}).get("pairs") or []

        fresh = []
        for p in pairs:
            try:
                created_ms = int(p.get("pairCreatedAt") or 0)
            except Exception:
                created_ms = 0

            # toma los creados en la ventana de tiempo
            if created_ms and (now_ms - created_ms) <= max_age_ms:
                fresh.append({
                    "tokenAddress": (p.get("baseToken") or {}).get("address"),
                    "symbol": (p.get("baseToken") or {}).get("symbol"),
                    "liquidity": p.get("liquidity") or {},
                    "url": p.get("url"),
                    "socials": p.get("socials") or [],
                    "raw": p,  # para debug opcional
                })

        # limita cantidad para no spamear
        return fresh[:limit]

