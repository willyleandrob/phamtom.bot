from __future__ import annotations
import time
from datetime import datetime, timezone
from typing import Dict, Any, List

from providers.dexscreener import DexScreener
from providers.telegram import TelegramBot
from main import load_config, normalize_symbol  # ya lo tienes en main.py


def short_liq(liq: float) -> str:
    try:
        if liq >= 1_000_000:
            return f"{liq/1_000_000:.2f}M"
        if liq >= 1_000:
            return f"{liq/1_000:.2f}k"
        return f"{liq:.0f}"
    except Exception:
        return str(liq)


def telegram_heartbeat(cfg: dict):
    tg = cfg.get("telegram", {}) or {}
    if not tg.get("bot_token") or not tg.get("chat_id"):
        return
    tb = TelegramBot(tg["bot_token"])
    msg = f"✅ Watcher ONLINE — {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}"
    tb.send_message(tg["chat_id"], msg)


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

    total_pairs = 0
    total_after_filters = 0

    for chain in chains:
        print(f"[{datetime.utcnow()}] Escaneando chain {chain} ...")
        try:
            # últimas 3 horas (ajustable)
            items = ds.get_new_tokens(chain, max_age_minutes=180, limit=200)
        except Exception as e:
            print("  Error al obtener pares:", e)
            continue

        print(f"  -> pares recientes recibidos: {len(items)}")
        total_pairs += len(items)

        for it in items:
            liq_usd = float((it.get("liquidity") or {}).get("usd") or 0)
            if liq_usd < min_liq:
                continue

            # social score simplificado (si trae twitter/telegram suma)
            socials = [s.lower() for s in (it.get("socials") or []) if isinstance(s, str)]
            hype = 2
            if any(("twitter.com" in s or "x.com" in s or "nitter.net" in s) for s in socials):
                hype += 1
            if any(("t.me" in s or "telegram.me" in s) for s in socials):
                hype += 1
            social_score = min(5, hype)

            if social_score < min_social:
                continue

            total_after_filters += 1

            if tb:
                symbol = it.get("symbol") or "TOKEN"
                token_addr = it.get("tokenAddress") or "-"
                url = it.get("url") or ""
                lines = [
                    f"🚀 <b>Nuevo listado</b> en <b>{chain}</b>",
                    f"Token: <code>{symbol}</code>",
                    f"Address: <code>{token_addr}</code>",
                    f"Liquidez: <b>${liq_usd:,.0f}</b> ({short_liq(liq_usd)})",
                    f"Social score: <b>{social_score}</b>",
                ]
                if url:
                    lines.append(url)
                sent = tb.send_message(tg["chat_id"], "\n".join(lines))
                print("  -> alerta enviada" if sent else "  -> fallo enviando alerta")

        print(f"  -> candidatos tras filtros: {total_after_filters}")

    if total_pairs == 0:
        print("⚠️  No se recibieron pares (posible rate limit o chain sin actividad).")
    elif total_after_filters == 0:
        print("ℹ️  Hubo pares, pero ninguno pasó tus reglas (liquidez/social). Prueba bajando umbrales temporalmente.")


def main():
    cfg = load_config()
    interval = int((cfg.get("watcher") or {}).get("scan_interval_minutes", 15))

    # Heartbeat de arranque
    telegram_heartbeat(cfg)

    while True:
        try:
            scan_for_new_tokens(cfg)
        except Exception as e:
            print("ERROR ciclo watcher:", e)
        time.sleep(interval * 60)


if __name__ == "__main__":
    main()
