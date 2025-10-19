from __future__ import annotations
import argparse
import os
from typing import Optional, Dict, Any, List

# Python 3.11+: tomllib. Si usas 3.10, instala tomli y cambia a `import tomli as tomllib`
import tomllib

from providers.dexscreener import DexScreener
from providers.ethplorer import Ethplorer
from providers.etherscan import Etherscan
from providers.social import SocialScanner
from providers.telegram import TelegramBot  # <-- NUEVO

from scoring import (
    score_liquidity,
    score_volume_24h,
    score_holders_top1,
    score_pair_age_days,
    score_contract_verified,
    score_contract_age_days,
    score_top10_concentration,
    score_burn_percent,
    score_social_hype,
    aggregate,
)


def load_config() -> dict:
    cfg = {"ethplorer": {"api_key": "freekey"}, "etherscan": {"api_key": None}, "telegram": {"bot_token": None, "chat_id": None}}
    if os.path.exists("config.toml"):
        with open("config.toml", "rb") as f:
            user_cfg = tomllib.load(f)
            for k, v in user_cfg.items():
                if isinstance(v, dict):
                    cfg.setdefault(k, {}).update(v)
                else:
                    cfg[k] = v
    return cfg


def fetch_from_dexscreener(chain: str, token: Optional[str], pair_url_or_addr: Optional[str]) -> Dict[str, Any]:
    ds = DexScreener()
    pair_data: Optional[Dict[str, Any]] = None
    if pair_url_or_addr:
        pair_addr = pair_url_or_addr
        if pair_url_or_addr.startswith("http"):
            parsed = ds.parse_pair_from_url(pair_url_or_addr)
            if parsed:
                pair_addr = parsed
        try:
            pair_data = ds.get_pair_by_address(chain, pair_addr)
        except Exception:
            pair_data = None

    if not pair_data and token:
        try:
            pair_data = ds.get_token_pairs(chain, token)
        except Exception:
            pair_data = None

    return pair_data or {}


def compute_top1_percent(holders_json: list, total_supply: float) -> Optional[float]:
    if not holders_json or not total_supply or total_supply <= 0:
        return None
    top1 = holders_json[0]
    bal = float(top1.get("balance", 0))
    return (bal / total_supply) * 100.0 if bal else None


def compute_top10_percent(holders_json: list, total_supply: float) -> Optional[float]:
    if not holders_json or not total_supply or total_supply <= 0:
        return None
    top10 = holders_json[:10]
    total = 0.0
    for h in top10:
        try:
            total += float(h.get("balance", 0))
        except Exception:
            pass
    return (total / total_supply) * 100.0 if total > 0 else None


def compute_burn_percent(holders_json: list, total_supply: float) -> Optional[float]:
    if not holders_json or not total_supply or total_supply <= 0:
        return None
    dead_like = {
        "0x0000000000000000000000000000000000000000",
        "0x000000000000000000000000000000000000dead",
        "0xdead000000000000000000000000000000000000",
    }
    burned = 0.0
    for h in holders_json:
        addr = (h.get("address") or "").lower()
        if addr in dead_like:
            try:
                burned += float(h.get("balance", 0))
            except Exception:
                pass
    return (burned / total_supply) * 100.0 if burned > 0 else 0.0


def first_or_none(items: List[str], keywords: List[str]) -> Optional[str]:
    if not items:
        return None
    lower = [i.lower() for i in items if isinstance(i, str)]
    for kw in keywords:
        for i, raw in enumerate(items):
            if isinstance(raw, str) and kw.lower() in lower[i]:
                return raw
    return None


def normalize_symbol(pair: Dict[str, Any], fallback: str = "crypto") -> str:
    sym = (pair.get("baseToken", {}) or {}).get("symbol") if pair else None
    if not sym:
        return fallback
    return "".join(ch for ch in sym if ch.isalnum()).upper()[:15] or fallback


def main():
    from rich import print
    from rich.table import Table
    from datetime import datetime, timezone
    import csv

    parser = argparse.ArgumentParser(description="Token Scanner (MVP + Tokenomics + Social + Telegram Alerts)")
    parser.add_argument("--chain", required=True, help="ethereum | bsc | polygon | solana (holders/tokenomics detallado solo en ethereum)")
    parser.add_argument("--token", help="address del token (0x...)")
    parser.add_argument("--pair", help="URL o address del par en DexScreener")
    parser.add_argument("--save-csv", help="ruta de salida CSV (opcional)", default=None)
    parser.add_argument("--alert", action="store_true", help="si se pasa, envía alerta por Telegram si supera el umbral")
    parser.add_argument("--threshold", type=float, default=3.5, help="umbral para alerta (default: 3.5)")
    args = parser.parse_args()

    cfg = load_config()

    # 1) DexScreener: liquidez y volumen
    pair = fetch_from_dexscreener(args.chain.lower(), args.token, args.pair)
    liq_usd = float(pair.get("liquidity", {}).get("usd", 0)) if pair else None
    vol24 = float(pair.get("volume", {}).get("h24", 0)) if pair else None

    # 2) Edad del par
    pair_age_days = None
    if pair and pair.get("pairCreatedAt"):
        try:
            created_ms = int(pair["pairCreatedAt"])
            created_dt = datetime.fromtimestamp(created_ms / 1000.0, tz=timezone.utc)
            now = datetime.now(tz=timezone.utc)
            pair_age_days = max((now - created_dt).days, 0)
        except Exception:
            pair_age_days = None

    # 3) Holders y tokenomics (solo Ethereum)
    percent_top1 = None
    percent_top10 = None
    burn_percent = None
    if args.chain.lower() == "ethereum" and args.token:
        ethp = Ethplorer(api_key=cfg.get("ethplorer", {}).get("api_key", "freekey"))
        info = ethp.get_token_info(args.token) or {}
        holders = ethp.get_top_holders(args.token, limit=50) or []
        total_supply_raw = info.get("totalSupply") or 0
        decimals = info.get("decimals") or 18
        try:
            total_supply = float(total_supply_raw) / (10 ** int(decimals))
        except Exception:
            total_supply = 0.0
        percent_top1 = compute_top1_percent(holders, total_supply)
        percent_top10 = compute_top10_percent(holders, total_supply)
        burn_percent = compute_burn_percent(holders, total_supply)

    # 4) Auditoría / verificación de contrato (solo Ethereum)
    contract_verified = None
    contract_age_days = None
    if args.chain.lower() == "ethereum" and args.token:
        etherscan_key = (cfg.get("etherscan", {}) or {}).get("api_key")
        if etherscan_key:
            es = Etherscan(api_key=etherscan_key)
            try:
                contract_verified = es.is_contract_verified(args.token)
            except Exception:
                contract_verified = None
            try:
                creation = es.get_contract_creation(args.token)
                if creation and creation.get("timeStamp"):
                    created_ts = int(creation["timeStamp"])
                    created_dt = datetime.fromtimestamp(created_ts, tz=timezone.utc)
                    now = datetime.now(tz=timezone.utc)
                    contract_age_days = max((now - created_dt).days, 0)
            except Exception:
                contract_age_days = None

    # 4.5) Comunidad y Marketing (X/Twitter + Social links + Telegram presence)
    social_score = None
    twitter_mentions = None
    socials: List[str] = []
    twitter_url = None
    telegram_url = None
    website_url = None

    try:
        ss = SocialScanner()
        socials = ss.get_from_dexscreener_socials(pair) or []
        twitter_url = first_or_none(socials, ["twitter.com", "x.com", "nitter.net"])
        telegram_url = first_or_none(socials, ["t.me", "telegram.me", "telegram.org"])
        website_url = first_or_none(socials, ["http://", "https://"])

        symbol = normalize_symbol(pair, fallback="crypto")
        twitter_mentions = ss.twitter_mentions(symbol, limit=30)
        base_hype = ss.compute_hype_score(twitter_mentions)
        bonus = 1 if telegram_url else 0
        social_score = max(1, min(5, (base_hype + bonus)))
    except Exception:
        social_score = None

    # 5) Scoring
    scores = {
        "Liquidez": score_liquidity(liq_usd if liq_usd is not None else 0.0),
        "Volumen 24h": score_volume_24h(vol24 if vol24 is not None else 0.0),
        "Top1 Holders": score_holders_top1(percent_top1 if percent_top1 is not None else 100.0),
        "TOP10 concentración": score_top10_concentration(percent_top10),
        "% Burn (dead/zero)": score_burn_percent(burn_percent),
        "Edad del par (días)": score_pair_age_days(pair_age_days),
        "Contrato verificado": score_contract_verified(contract_verified),
        "Edad del contrato (días)": score_contract_age_days(contract_age_days),
        "Hype Social (X/Twitter)": score_social_hype(social_score),
    }

    avg, rec = aggregate(scores)

    # 6) Salida en tablas
    table = Table(title="Puntaje del Token (MVP + Tokenomics + Social + Telegram Alerts)")
    table.add_column("Categoría", justify="left")
    table.add_column("Puntaje (1–5)", justify="center")
    for k, v in scores.items():
        table.add_row(k, str(v))
    print(table)
    print(f"[bold]Promedio:[/bold] {avg}  |  [bold]Recomendación:[/bold] {rec}")

    extra = Table(title="Datos base")
    extra.add_column("Métrica")
    extra.add_column("Valor")
    if liq_usd is not None:
        extra.add_row("Liquidez (USD)", f"{liq_usd:,.2f}")
    if vol24 is not None:
        extra.add_row("Volumen 24h (USD)", f"{vol24:,.2f}")
    if percent_top1 is not None:
        extra.add_row("% Top1 Holder", f"{percent_top1:.2f}%")
    if percent_top10 is not None:
        extra.add_row("% TOP10", f"{percent_top10:.2f}%")
    if burn_percent is not None:
        extra.add_row("% Burn", f"{burn_percent:.2f}%")
    if pair_age_days is not None:
        extra.add_row("Edad del par (días)", str(pair_age_days))
    if contract_verified is not None:
        extra.add_row("Contrato verificado", "Sí" if contract_verified else "No")
    if contract_age_days is not None:
        extra.add_row("Edad del contrato (días)", str(contract_age_days))
    if twitter_mentions is not None:
        extra.add_row("Menciones X/Twitter (estimado)", str(twitter_mentions))
    if social_score is not None:
        extra.add_row("Hype Social (score)", str(social_score))
    if website_url:
        extra.add_row("Sitio/Web", website_url)
    if twitter_url:
        extra.add_row("Twitter/X", twitter_url)
    if telegram_url:
        extra.add_row("Telegram", telegram_url)
    print(extra)

    # 7) CSV opcional
    if args.save_csv:
        outpath = args.save_csv
        headers = [
            "chain","token","pair_liquidity_usd","pair_volume_24h_usd",
            "top1_percent","top10_percent","burn_percent","pair_age_days",
            "contract_verified","contract_age_days","twitter_mentions",
            "social_score","website_url","twitter_url","telegram_url",
            "avg_score","recommendation",
        ]
        row = [
            args.chain,
            args.token or (pair.get("baseToken", {}).get("address") if pair else None),
            liq_usd, vol24, percent_top1, percent_top10, burn_percent, pair_age_days,
            contract_verified, contract_age_days, twitter_mentions, social_score,
            website_url, twitter_url, telegram_url, avg, rec,
        ]
        try:
            file_exists = os.path.exists(outpath)
            with open(outpath, "a", newline="", encoding="utf-8") as f:
                import csv
                w = csv.writer(f)
                if not file_exists:
                    w.writerow(headers)
                w.writerow(row)
            print(f"[green]CSV guardado en:[/green] {outpath}")
        except Exception as e:
            print(f"[yellow]No se pudo guardar CSV:[/yellow] {e}")

    # 8) Alerta por Telegram si procede
    if args.alert:
        bot_token = (cfg.get("telegram", {}) or {}).get("bot_token")
        chat_id   = (cfg.get("telegram", {}) or {}).get("chat_id")
        if bot_token and chat_id and avg >= args.threshold:
            tb = TelegramBot(bot_token)
            # mensaje compacto
            symbol = normalize_symbol(pair, fallback="TOKEN")
            title = f"🔥 ALARMA {symbol} — score {avg} ({rec})"
            lines = [
                f"<b>{title}</b>",
                f"Chain: <code>{args.chain}</code>",
                f"Token: <code>{args.token or 'N/A'}</code>",
                f"Liquidez: <b>{(liq_usd or 0):,.0f} USD</b> | Vol 24h: <b>{(vol24 or 0):,.0f} USD</b>",
                f"Top1: <b>{(percent_top1 or 0):.2f}%</b> | Top10: <b>{(percent_top10 or 0):.2f}%</b> | Burn: <b>{(burn_percent or 0):.2f}%</b>",
                f"Contrato verificado: <b>{'Sí' if contract_verified else 'No' if contract_verified is not None else 'Desconocido'}</b>",
                f"Social (score): <b>{social_score if social_score is not None else 'N/A'}</b> | Menciones X: <b>{twitter_mentions if twitter_mentions is not None else 'N/A'}</b>",
                f"Recomendación: <b>{rec}</b>",
            ]
            # si hay links útiles
            if website_url or telegram_url or (pair.get('url') if pair else None):
                lines.append("")
                if website_url:
                    lines.append(f"🌐 {website_url}")
                if telegram_url:
                    lines.append(f"📣 {telegram_url}")
                pair_url = (pair.get("url") if pair else None)
                if pair_url:
                    lines.append(f"📊 {pair_url}")

            sent = tb.send_message(chat_id, "\n".join(lines))
            if sent:
                print("[green]Alerta Telegram enviada.[/green]")
            else:
                print("[yellow]No se pudo enviar la alerta por Telegram.[/yellow]")


if __name__ == "__main__":
    main()

