from __future__ import annotations
import time
import tomllib
import os
from datetime import datetime

from providers.dexscreener import DexScreener
from providers.telegram import TelegramBot
from scoring import score_social_hype, aggregate  # importar lo necesario
from main import load_config, normalize_symbol  # asumimos main.py tiene normalize_symbol

def scan_for_new_tokens(cfg: dict):
    ds = DexScreener()
    bot_token = cfg["telegram"]["bot_token"]
    chat_id   = cfg["telegram"]["chat_id"]
    tb = TelegramBot(bot_token) if (bot_token and chat_id) else None

    chains = cfg["watcher"]["chains"]
    min_liq = cfg["watcher"]["min_liquidity_usd"]
    min_social = cfg["watcher"]["min_social_score"]

    for chain in chains:
        print(f"[{datetime.utcnow()}] Escaneando chain {chain} ...")
        try:
            r = ds.get_new_tokens(chain)  # **Importante**: este método lo tendrías que implementar en dexscreener.py
        except Exception as e:
            print("Error al obtener nuevos tokens:", e)
            continue

        for token_info in r:
            address = token_info.get("tokenAddress")
            symbol  = token_info.get("symbol") or "UNKNOWN"
            pair_liq = float(token_info.get("liquidity", {}).get("usd", 0) or 0)
            print(f"  Token {symbol} ({address}) liquidez {pair_liq:.0f} USD")

            if pair_liq < min_liq:
                continue

            socials = token_info.get("socials", [])
            # calc social score rápido: si incluyó twitter URL -> +1, etc.
            hype = 2
            if any("twitter.com" in s.lower() or "x.com" in s.lower() for s in socials):
                hype += 1
            # placeholder: convertir hype en escala 1-5
            social_score = min(5, hype)

            if social_score < min_social:
                continue

            # enviar alerta
            if tb:
                title = f"🚀 Nuevo token listado: {symbol} en {chain}"
                body = [
                    f"<b>{title}</b>",
                    f"Token: <code>{address}</code>",
                    f"Liquidez: <b>{pair_liq:,.0f} USD</b>",
                    f"Social score estimado: <b>{social_score}</b>",
                    f"Link: {token_info.get('url')}"
                ]
                sent = tb.send_message(chat_id, "\n".join(body))
                print("  Alerta enviada." if sent else "  Error enviando alerta.")

def main():
    cfg = load_config()
    interval = cfg["watcher"]["scan_interval_minutes"]
    while True:
        scan_for_new_tokens(cfg)
        time.sleep(interval * 60)

if __name__ == "__main__":
    main()
