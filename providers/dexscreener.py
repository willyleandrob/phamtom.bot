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
    def get_new_tokens(self, chain: str, limit: int = 50) -> list:
        """
        Retorna lista de tokens recientemente listados en la cadena dada.
        Devuelve estructuras tipo:
        {
            'tokenAddress': '0x...',
            'symbol': 'ABC',
            'liquidity': {'usd': 12345.67},
            'url': 'https://dexscreener.com/chain/0xPAIR',
            'socials': [...]
        }
        """
        url = f"https://api.dexscreener.com/latest/dex/search?q=&chain={chain}"
        r = requests.get(url, timeout=20)
        if r.status_code != 200:
            return []
        data = r.json().get("pairs") or []
        results = []
        for p in data[:limit]:
            results.append({
                'tokenAddress': p.get('baseToken', {}).get('address'),
                'symbol': p.get('baseToken', {}).get('symbol'),
                'liquidity': p.get('liquidity', {}),
                'url': p.get('url'),
                'socials': p.get('socials') or []
            })
        return results
