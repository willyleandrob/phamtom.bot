# watcher.py
# ------------------------------------------------------------
# Escáner automático 24/7:
#  - Lee config.toml (vía main.load_config)
#  - Cada X minutos escanea chains definidas
#  - Filtra por liquidez mínima y "hype social" simple
#  - Envía alertas por Telegram
#  - Muestra contadores útiles en logs
# ------------------------------------------------------------

from __future__ import annotations

import time
from datetime import datetime, timezone
from typing import Dict, Any, List

from providers.dexscreener import DexScreener
from providers.telegram import TelegramBot
from main import load_config  # ya lo tienes en tu proyecto


# ------------ Utilidades de formato ------------

def short_liq(liq: float) -> str:
    """Convierte 1234567 -> 1.23M, 12345 -> 12.35k, etc."""
    try:
        if liq >= 1_000_000:
            return f"{liq/1_000_000:.2f}M"
        if liq >= 1_000:
            return f"{liq/1_000:.2f}k"
        return f"{liq:.0f}"
    except Exception:
        return str(liq)


def utc_now_str() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")


# ------------ Telegram helpers ------------

def telegram_heartbeat(cfg: dict):
    """Envía un ping de 'estoy vivo' al iniciar el watcher."""
    tg = cfg.get("telegram", {}) or {}
    if not tg.get("bot_token") or not tg.get("chat_id"):
        return
    tb = TelegramBot(tg["bot_token"])
    msg = f"✅ Watcher ONLINE — {utc_now_str()}"
    tb.send_message(tg["chat_id"], msg)


def telegram_alert(tb: TelegramBot, chat_id: str, chain: str, item: dict, liq_usd: float, social_score: int):
    symbol = item.get("symbol") or "TOKEN"
    token_addr = item.get("tokenAddress") or "-"
    url = item.get("url") or ""
    lines = [
        f"🚀 <b>Nuevo listado</b> en <b>{chain}</b>",
        f"Token: <code>{symbol}</code>",
        f"Address: <code>{token_addr}</code>",
        f"Liquidez: <b>${liq_usd:,.0f}</b> ({short_liq(liq_usd)})",
        f"Social score: <b>{social_score}</b>",
    ]
    if url:
        lines.append(url)
    tb.send_message(chat_id, "\n".join(lines))


# ------------ Núcleo del escaneo ------------

def scan_for_new_tokens(cfg: dict):
    ds = DexScreener()

    tg = cfg.get("telegram", {}) or {}
    watcher = cfg.get("watcher", {}) or {}
    chains = watcher.get("chains", ["ethereum"])
    min_liq = float(watcher.get("min_liquidity_usd", 50000))
    min_social = float(watcher.get("min_social_score", 4.0))

    tb = None
    if tg.get("bot_token") and tg.get("chat_id"):
        tb = TelegramBot(tg["bot_token"])

    total_pairs_global = 0
    total_after_filters_global = 0

    for chain in chains:
        print(f"[{utc_now_str()}] Escaneando chain {chain} ...")
        try:
            # últimas 3 h por defecto, puedes ajustar aquí si quieres
            items = ds.get_new_tokens(chain, max_age_minutes=180, limit=200)
        except Exception as e:
            print(f"  ! Error al obtener pares: {e}")
            continue

        print(f"  -> pares recientes recibidos: {len(items)}")
        total_pairs_global += len(items)

        candidatos_chain = 0

        for it in items:
            liq_usd = float((it.get("liquidity") or {}).get("usd") or 0)
            if liq_usd < min_liq:
                continue

            # Hype social MUY simple: si vemos twitter/x y telegram, sube el score
            socials = [s.lower() for s in (it.get("socials") or []) if isinstance(s, str)]
            hype = 2
            if any(("twitter.com" in s or "x.com" in s or "nitter.net" in s) for s in socials):
                hype += 1
            if any(("t.me" in s or "telegram.me" in s) for s in socials):
                hype += 1
            social_score = min(5, hype)

            if social_score < min_social:
                continue

            candidatos_chain += 1
            total_after_filters_global += 1

            if tb:
                try:
                    telegram_alert(tb, tg["chat_id"], chain, it, liq_usd, social_score)
                    print("  -> alerta enviada")
                except Exception as e:
                    print(f"  -> fallo enviando alerta: {e}")

        print(f"  -> candidatos tras filtros en {chain}: {candidatos_chain}")

    if total_pairs_global == 0:
        print("⚠️  No se recibieron pares (posible rate limit o poca actividad).")
    elif total_after_filters_global == 0:
        print("ℹ️  Hubo pares, pero ninguno pasó tus reglas. Considera bajar min_liquidity_usd o min_social_score temporalmente.")


def main():
    cfg = load_config()
    interval = int((cfg.get("watcher") or {}).get("scan_interval_minutes", 15))

    # Heartbeat de arranque
    telegram_heartbeat(cfg)

    while True:
        try:
            scan_for_new_tokens(cfg)
        except Exception as e:
            print(f"ERROR ciclo watcher: {e}")
        time.sleep(interval * 60)


if __name__ == "__main__":
    main()
