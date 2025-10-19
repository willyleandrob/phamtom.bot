# scoring.py
from typing import Dict, Any, Optional, Tuple


def score_liquidity(usd: float) -> int:
    if usd is None:
        return 1
    if usd < 50_000:
        return 2
    if usd < 150_000:
        return 3
    if usd < 500_000:
        return 4
    return 5


def score_volume_24h(usd: float) -> int:
    if usd is None:
        return 1
    if usd < 20_000:
        return 2
    if usd < 100_000:
        return 3
    if usd < 500_000:
        return 4
    return 5


def score_holders_top1(percent_top1: float) -> int:
    if percent_top1 is None:
        return 1
    if percent_top1 > 20:
        return 1
    if percent_top1 > 10:
        return 2
    if percent_top1 > 5:
        return 3
    if percent_top1 > 2:
        return 4
    return 5


def score_pair_age_days(days: Optional[int]) -> int:
    if days is None:
        return 2
    if days < 2:
        return 2
    if days < 7:
        return 3
    if days < 30:
        return 4
    return 5


def score_contract_verified(verified: Optional[bool]) -> int:
    if verified is None:
        return 3
    return 5 if verified else 2


def score_contract_age_days(days: Optional[int]) -> int:
    if days is None:
        return 3
    if days < 2:
        return 2
    if days < 7:
        return 3
    if days < 30:
        return 4
    return 5


# ==== NUEVO: TOKENOMICS ====

def score_top10_concentration(percent_top10: Optional[float]) -> int:
    """
    Menos concentración en TOP10 = mejor.
    """
    if percent_top10 is None:
        return 2
    if percent_top10 > 80:
        return 1
    if percent_top10 > 60:
        return 2
    if percent_top10 > 40:
        return 3
    if percent_top10 > 25:
        return 4
    return 5


def score_burn_percent(burn_pct: Optional[float]) -> int:
    """
    % quemado (dead/zero). Algo de burn suele ser positivo.
    """
    if burn_pct is None:
        return 3
    if burn_pct < 1:
        return 2
    if burn_pct < 5:
        return 3
    if burn_pct < 20:
        return 4
    return 5


def aggregate(scores: Dict[str, int]) -> Tuple[float, str]:
    vals = list(scores.values()) if scores else [1]
    avg = sum(vals) / len(vals) if vals else 1.0
    if avg < 2.5:
        rec = "🚫 Evitar"
    elif avg < 3.5:
        rec = "⚠️ Especulativo"
    else:
        rec = "✅ Aceptable"
    return round(avg, 2), rec

def score_social_hype(hype_score: int) -> int:
    if hype_score is None:
        return 2
    return hype_score
