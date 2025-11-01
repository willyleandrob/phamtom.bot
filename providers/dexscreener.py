# providers/dexscreener.py
# ------------------------------------------------------------
# Cliente ligero para la API pública de DexScreener.
# Incluye utilidades para:
#  - Buscar par por address
#  - Buscar pares donde el baseToken sea el token dado
#  - Extraer redes sociales adjuntas a un par
#  - Listar pares recientes por chain y filtrar por "edad"
# ------------------------------------------------------------

from __future__ import annotations

import re
import time
from typing import Any, Dict, List, Optional

import requests


class DexScreener:
    BASE = "https://api.dexscreener.com/latest/dex"

    def __init__(self, timeout: int = 25):
        self.timeout = timeout
        # Headers simples para evitar bloqueos por user-agent
        self.headers = {
            "User-Agent": "Mozilla/5.0 (compatible; TinokWatcher/1.0; +tinok)",
            "Accept": "application/json",
        }

    # ----------------------- Helpers -----------------------

    def _get(self, url: str, params: Optional[Dict[str, Any]] = None, retries: int = 2) -> Optional[Dict[str, Any]]:
        """
        GET con reintentos simples y manejo de errores.
        Devuelve dict JSON o None.
        """
        for attempt in range(retries + 1):
            try:
                r = requests.get(url, params=params, headers=self.headers, timeout=self.timeout)
                # Si rate-limit (429) o error 5xx, reintenta
                if r.status_code >= 500 or r.status_code == 429:
                    time.sleep(1.5 * (attempt + 1))
                    continue
                if r.status_code != 200:
                    return None
                return r.json()
            except requests.RequestException:
                time.sleep(1.0 * (attempt + 1))
        return None

    @staticmethod
    def _to_float(x: Any, default: float = 0.0) -> float:
        try:
            if x is None or x == "":
                return default
            return float(x)
        except Exception:
            return default

    @staticmethod
    def _socials_from_any(value: Any) -> List[str]:
        """
        Extrae URLs de un campo que a veces es str, list o dict.
        """
        out: List[str] = []
        if isinstance(value, str):
            out.append(value)
        elif isinstance(value, list):
            out.extend([v for v in value if isinstance(v, str)])
        elif isinstance(value, dict):
            out.extend([v for v in value.values() if isinstance(v, str)])
        # Filtra a solo URLs
        return [s for s in out if isinstance(s, str) and s.startswith(("http://", "https://"))]

    # ----------------------- Parsers -----------------------

    def parse_pair_from_url(self, url: str) -> Optional[str]:
        """
        https://dexscreener.com/ethereum/0xPAIRADDRESS -> 0xPAIRADDRESS
        """
        if not url:
            return None
        # Busca la última "palabra" tipo address al final de la URL
        m = re.search(r"/(0x[a-fA-F0-9]{20,})/?$", url.strip())
        if m:
            return m.group(1)
        # Fallback: último segmento
        try:
            return url.rstrip("/").split("/")[-1]
        except Exception:
            return None

    # ----------------------- Endpoints públicos -----------------------

    def get_pair_by_address(self, chain: str, pair_addr: str) -> Dict[str, Any]:
        """
        Retorna el primer par para {chain}/{pair_addr}.
        """
        url = f"{self.BASE}/pairs/{chain}/{pair_addr}"
        data = self._get(url)
        if not data:
            return {}
        pairs = data.get("pairs") or []
        return pairs[0] if pairs else {}

    def get_token_pairs(self, chain: str, token_addr: str) -> Dict[str, Any]:
        """
        Busca pares donde el baseToken sea token_addr usando /search?q=.
        Devuelve el primer match donde baseToken.address == token_addr.
        """
        url = f"{self.BASE}/search"
        data = self._get(url, params={"q": token_addr})
        if not data:
            return {}
        for p in data.get("pairs", []):
            base = p.get("baseToken") or {}
            if (base.get("address") or "").lower() == token_addr.lower():
                return p
        return {}

    def get_from_pair_socials(self, pair: Dict[str, Any]) -> List[str]:
        """
        Intenta extraer enlaces sociales del objeto par.
        """
        if not pair:
            return []
        out: List[str] = []
        for field in ("socials", "info", "website", "url"):
            if field in pair:
                out.extend(self._socials_from_any(pair.get(field)))
        # Quita duplicados preservando orden
        seen = set()
        uniq = []
        for s in out:
            if s not in seen:
                seen.add(s)
                uniq.append(s)
        return uniq

    # ----------------------- Explorador de "nuevos" -----------------------

    def get_new_tokens(
        self,
        chain: str,
        max_age_minutes: int = 180,
        limit: int = 200,
    ) -> List[Dict[str, Any]]:
        """
        Obtiene pares recientes de una chain con /pairs/{chain} y filtra por edad del par.

        - max_age_minutes: ventana de "novedad" (por defecto 3h).
        - limit: recorta el listado final.

        Devuelve entries con:
        {
          'tokenAddress': str,
          'symbol': str,
          'liquidity': {'usd': float},
          'url': str,
          'socials': [str, ...],
          'raw': {...}   # objeto original para debug
        }
        """
        url = f"{self.BASE}/pairs/{chain}"
        data = self._get(url)
        if not data:
            return []

        now_ms = int(time.time() * 1000)
        max_age_ms = int(max_age_minutes * 60 * 1000)
        pairs = data.get("pairs") or []

        results: List[Dict[str, Any]] = []
        for p in pairs:
            try:
                created_ms = int(p.get("pairCreatedAt") or 0)
            except Exception:
                created_ms = 0

            # Considera "nuevo" si el par fue creado dentro de la ventana
            is_fresh = created_ms and ((now_ms - created_ms) <= max_age_ms)

            if not is_fresh:
                continue

            base = p.get("baseToken") or {}
            liq_obj = p.get("liquidity") or {}
            liq_usd = self._to_float(liq_obj.get("usd"), 0.0)

            results.append(
                {
                    "tokenAddress": base.get("address"),
                    "symbol": base.get("symbol"),
                    "liquidity": {"usd": liq_usd},
                    "url": p.get("url"),
                    "socials": p.get("socials") or [],
                    "raw": p,
                }
            )

        # Recorta
        return results[:limit]

