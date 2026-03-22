from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any


def parse_json_array(raw: str | None) -> list[Any]:
    if not raw:
        return []
    try:
        value = json.loads(raw)
    except json.JSONDecodeError:
        return []
    return value if isinstance(value, list) else []


def market_token_rows(market: dict[str, Any]) -> list[dict[str, Any]]:
    outcomes = market.get("outcomes")
    outcome_prices = market.get("outcomePrices")
    token_ids = market.get("clobTokenIds")

    if isinstance(outcomes, str):
        outcomes = parse_json_array(outcomes)
    if isinstance(outcome_prices, str):
        outcome_prices = parse_json_array(outcome_prices)
    if isinstance(token_ids, str):
        token_ids = parse_json_array(token_ids)

    rows = []
    for idx, token_id in enumerate(token_ids or []):
        price = outcome_prices[idx] if idx < len(outcome_prices or []) else None
        rows.append(
            {
                "index": idx,
                "outcome": outcomes[idx] if idx < len(outcomes or []) else None,
                "price": coerce_float(price),
                "token_id": token_id,
            }
        )
    return rows


def parse_datetime(value: Any) -> datetime | None:
    if value in (None, ""):
        return None
    if isinstance(value, (int, float)):
        return datetime.fromtimestamp(float(value), tz=UTC)
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return None
        if text.isdigit():
            return datetime.fromtimestamp(int(text), tz=UTC)
        if text.endswith("Z"):
            text = f"{text[:-1]}+00:00"
        try:
            parsed = datetime.fromisoformat(text)
        except ValueError:
            return None
        if parsed.tzinfo is None:
            return parsed.replace(tzinfo=UTC)
        return parsed.astimezone(UTC)
    return None


def format_timestamp(value: Any) -> str:
    parsed = parse_datetime(value)
    if not parsed:
        return ""
    return parsed.astimezone(UTC).isoformat().replace("+00:00", "Z")


def to_unix_seconds(value: Any) -> int | None:
    parsed = parse_datetime(value)
    if not parsed:
        return None
    return int(parsed.timestamp())


def parse_duration_to_seconds(value: str | None) -> int | None:
    if not value:
        return None
    text = value.strip().lower()
    if not text:
        return None
    if text.isdigit():
        amount = int(text)
        return amount * 60 if amount > 0 else None
    units = {"m": 60, "h": 3600, "d": 86400, "w": 604800}
    unit = text[-1]
    if unit not in units:
        return None
    try:
        amount = int(text[:-1])
    except ValueError:
        return None
    if amount <= 0:
        return None
    return amount * units[unit]


def coerce_float(value: Any) -> float | None:
    if value in (None, ""):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def summarize_market(market: dict[str, Any]) -> dict[str, Any]:
    rows = market_token_rows(market)
    liquidity = coerce_float(market.get("liquidityNum") or market.get("liquidity"))
    volume24hr = coerce_float(market.get("volume24hrClob") or market.get("volume24hr"))
    summary = {
        "id": market.get("id"),
        "slug": market.get("slug"),
        "question": market.get("question"),
        "active": market.get("active"),
        "closed": market.get("closed"),
        "archived": market.get("archived"),
        "acceptingOrders": market.get("acceptingOrders"),
        "conditionId": market.get("conditionId"),
        "endDate": market.get("endDate") or market.get("endDateIso"),
        "liquidity": liquidity,
        "volume24hr": volume24hr,
        "startDate": market.get("startDate") or market.get("startDateIso"),
        "resolved": bool(market.get("id") and market.get("conditionId")),
        "odds": rows,
        "tokens": rows,
    }
    ranking = market.get("_ranking")
    if isinstance(ranking, dict):
        summary.update(
            {
                "rankField": ranking.get("rankField"),
                "rankValue": ranking.get("rankValue"),
                "rankingResolved": ranking.get("rankingResolved"),
                "rankingSource": ranking.get("rankingSource"),
                "rankingFallbackUsed": ranking.get("rankingFallbackUsed"),
            }
        )
    ranking_context = market.get("_rankingContext")
    if isinstance(ranking_context, dict):
        summary.update(
            {
                "rankingDegraded": ranking_context.get("rankingDegraded"),
                "rankingIncompleteCount": ranking_context.get("rankingIncompleteCount"),
                "rankingDegradedReason": ranking_context.get("rankingDegradedReason"),
            }
        )
    return summary


def to_pretty_json(data: Any) -> str:
    return json.dumps(data, indent=2, sort_keys=False)
