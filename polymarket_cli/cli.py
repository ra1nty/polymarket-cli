from __future__ import annotations

import argparse
from typing import Any

from .api import HISTORY_INTERVALS, PolymarketClient
from .formatting import (
    coerce_float,
    format_timestamp,
    market_token_rows,
    parse_datetime,
    parse_duration_to_seconds,
    summarize_market,
    to_pretty_json,
    to_unix_seconds,
)

MARKET_SORT_CHOICES = ["volume24hr", "volume", "liquidity", "startDate", "endDate", "competitive", "closedTime"]
HISTORY_FORMAT_CHOICES = ["points", "ohlc", "summary"]


def _positive_int(value: str) -> int:
    parsed = int(value)
    if parsed <= 0:
        raise argparse.ArgumentTypeError("value must be > 0")
    return parsed


def _non_negative_float(value: str) -> float:
    parsed = float(value)
    if parsed < 0:
        raise argparse.ArgumentTypeError("value must be >= 0")
    return parsed


def _history_window(value: str) -> str:
    if parse_duration_to_seconds(value) is None:
        raise argparse.ArgumentTypeError(
            "window must be a positive minute count like 60, or a duration like 15m, 1h, 1d, or 1w"
        )
    return value


def _add_market_selector(parser: argparse.ArgumentParser, *, required: bool = True) -> None:
    group = parser.add_mutually_exclusive_group(required=required)
    group.add_argument("--slug", help="Polymarket market slug")
    group.add_argument("--id", help="Polymarket market id")


def _add_market_filter_arguments(parser: argparse.ArgumentParser, *, allow_query: bool) -> None:
    if allow_query:
        parser.add_argument("query", nargs="?", default=None, help="Optional free-text market query")
    parser.add_argument("--limit", type=_positive_int, default=10, help="Maximum markets to return")
    parser.add_argument("--offset", type=int, default=0, help="Gamma pagination offset")
    parser.add_argument(
        "--sort",
        choices=MARKET_SORT_CHOICES,
        default="volume24hr",
        help="Market sort field. Server-side when supported, otherwise normalized client-side.",
    )
    parser.add_argument("--ascending", action="store_true", help="Return lower values / earlier dates first")
    status = parser.add_mutually_exclusive_group()
    status.add_argument("--active-only", action="store_true", help="Only active, non-closed markets (default)")
    status.add_argument("--closed-only", action="store_true", help="Only closed markets")
    status.add_argument("--all", action="store_true", help="Do not apply the default active-only market filter")
    parser.add_argument(
        "--archived",
        action="store_true",
        help="Filter for archived markets only. Archived filtering is server-side.",
    )
    parser.add_argument(
        "--tag-id",
        action="append",
        default=[],
        help="Gamma tag id filter. Repeat to require multiple tags.",
    )
    parser.add_argument(
        "--exclude-tag-id",
        action="append",
        default=[],
        help="Exclude markets with these tag ids. Repeatable.",
    )
    parser.add_argument(
        "--related-tags",
        action="store_true",
        help="Request related-tag expansion alongside --tag-id where supported by Gamma.",
    )
    parser.add_argument("--start-after", help="Client-side filter on market startDate/startDateIso")
    parser.add_argument("--start-before", help="Client-side filter on market startDate/startDateIso")
    parser.add_argument("--end-after", help="Client-side filter on market endDate/endDateIso")
    parser.add_argument("--end-before", help="Client-side filter on market endDate/endDateIso")
    parser.add_argument("--min-liquidity", type=_non_negative_float, help="Client-side minimum liquidity")
    parser.add_argument("--max-liquidity", type=_non_negative_float, help="Client-side maximum liquidity")
    parser.add_argument("--min-volume24hr", type=_non_negative_float, help="Client-side minimum 24h volume")
    parser.add_argument("--max-volume24hr", type=_non_negative_float, help="Client-side maximum 24h volume")
    parser.add_argument(
        "--hydrate",
        action="store_true",
        help="Hydrate matching markets to full market detail before rendering/filtering locally.",
    )
    parser.add_argument(
        "--with-odds",
        action="store_true",
        help="Include current token odds in output. Implies market hydration for search/list.",
    )
    parser.add_argument(
        "--with-market",
        action="store_true",
        help="Include the resolved raw market payload in JSON output. Implies market hydration for search/list.",
    )
    parser.add_argument("--json", action="store_true", help="Emit JSON instead of tabular text")


def _resolve_market(client: PolymarketClient, args: argparse.Namespace) -> dict[str, Any]:
    return client.get_market(slug=args.slug, market_id=args.id)


def _resolve_condition_id(client: PolymarketClient, args: argparse.Namespace) -> str:
    if getattr(args, "condition_id", None):
        return args.condition_id
    if not (getattr(args, "slug", None) or getattr(args, "id", None)):
        raise SystemExit("Provide --condition-id or a market selector (--slug/--id)")
    market = _resolve_market(client, args)
    condition_id = market.get("conditionId")
    if not condition_id:
        raise SystemExit("No condition id found on selected market")
    return str(condition_id)


def _resolve_token_id(client: PolymarketClient, args: argparse.Namespace) -> str:
    if getattr(args, "token_id", None):
        return args.token_id
    if not (getattr(args, "slug", None) or getattr(args, "id", None)):
        raise SystemExit("Provide --token-id or a market selector (--slug/--id)")
    market = _resolve_market(client, args)
    tokens = market_token_rows(market)
    if not tokens:
        raise SystemExit("No token ids found on selected market")
    if getattr(args, "outcome", None):
        for row in tokens:
            if str(row.get("outcome", "")).lower() == args.outcome.lower():
                return str(row["token_id"])
        raise SystemExit(f"Outcome not found: {args.outcome}")
    return str(tokens[0]["token_id"])


def _resolve_market_filters(args: argparse.Namespace) -> dict[str, Any]:
    if args.closed_only:
        active = None
        closed = True
    elif args.all:
        active = None
        closed = None
    else:
        active = True
        closed = False
    if args.archived:
        active = None if active is True else active
        closed = True if closed is False else closed
        archived = True
    else:
        archived = False if not args.all and not args.closed_only else None
    return {
        "limit": args.limit,
        "offset": args.offset,
        "active": active,
        "closed": closed,
        "archived": archived,
        "order": args.sort,
        "ascending": args.ascending,
        "tag_ids": args.tag_id or None,
        "exclude_tag_ids": args.exclude_tag_id or None,
        "related_tags": args.related_tags,
        "start_after": args.start_after,
        "start_before": args.start_before,
        "end_after": args.end_after,
        "end_before": args.end_before,
        "min_liquidity": args.min_liquidity,
        "max_liquidity": args.max_liquidity,
        "min_volume24hr": args.min_volume24hr,
        "max_volume24hr": args.max_volume24hr,
        "hydrate": bool(args.hydrate or args.with_odds or args.with_market),
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="polymarket-cli",
        description="Read-only Polymarket Gamma + CLOB CLI for market discovery, price snapshots, trades, and history",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p_search = sub.add_parser("search", help="Search markets with public Gamma filters")
    _add_market_filter_arguments(p_search, allow_query=True)

    p_list = sub.add_parser("list", help="List markets with public Gamma filters")
    _add_market_filter_arguments(p_list, allow_query=False)

    p_market = sub.add_parser("market", help="Fetch market details by slug or id")
    _add_market_selector(p_market, required=True)
    p_market.add_argument("--json", action="store_true")

    for name, help_text in [("book", "Fetch order book"), ("midpoint", "Fetch midpoint"), ("price", "Fetch last trade price")]:
        p = sub.add_parser(name, help=help_text)
        p.add_argument("--token-id")
        p.add_argument("--outcome", help="Outcome name to resolve token id when using a market selector")
        _add_market_selector(p, required=False)
        p.add_argument("--json", action="store_true")

    p_history = sub.add_parser("history", help="Fetch public CLOB price history for a token")
    p_history.add_argument("--token-id")
    p_history.add_argument("--outcome", help="Outcome name to resolve token id when using a market selector")
    _add_market_selector(p_history, required=False)
    p_history.add_argument("--interval", choices=sorted(HISTORY_INTERVALS), default="1d")
    p_history.add_argument("--fidelity", type=_positive_int, default=60, help="Sampling fidelity in minutes")
    p_history.add_argument("--start", help="Unix seconds or ISO-8601 timestamp passed to startTs")
    p_history.add_argument("--end", help="Unix seconds or ISO-8601 timestamp passed to endTs")
    p_history.add_argument(
        "--window",
        type=_history_window,
        help="Local aggregation window for --format ohlc/summary. Accepts bare minutes (60) or durations (15m, 1h, 1d, 1w).",
    )
    p_history.add_argument("--format", choices=HISTORY_FORMAT_CHOICES, default="points")
    p_history.add_argument("--json", action="store_true")

    p_trades = sub.add_parser("trades", help="Fetch recent public trades")
    p_trades.add_argument("--condition-id")
    _add_market_selector(p_trades, required=False)
    p_trades.add_argument("--limit", type=_positive_int, default=20)
    p_trades.add_argument("--json", action="store_true")

    return parser


def _render_market_table(markets: list[dict[str, Any]], *, with_odds: bool = False) -> str:
    lines = []
    for market in markets:
        status = []
        if market.get("active"):
            status.append("active")
        if market.get("closed"):
            status.append("closed")
        if market.get("archived"):
            status.append("archived")
        odds = ""
        if with_odds:
            odds = " | ".join(
                f"{row.get('outcome')}={row.get('price')}"
                for row in market.get("odds", [])
                if row.get("outcome") is not None and row.get("price") is not None
            )
        lines.append(
            "\t".join(
                [
                    str(market.get("id") or ""),
                    str(market.get("slug") or ""),
                    str(market.get("question") or ""),
                    ",".join(status) or "open",
                    str(market.get("endDate") or ""),
                    str(market.get("liquidity") or ""),
                    str(market.get("volume24hr") or ""),
                    odds,
                ]
            )
        )
    return "\n".join(lines)


def _normalize_history_points(payload: dict[str, Any]) -> list[dict[str, Any]]:
    history = payload.get("history") or []
    points = []
    for row in history:
        if not isinstance(row, dict):
            continue
        timestamp = row.get("t") or row.get("timestamp") or row.get("time")
        price = row.get("p") or row.get("price")
        dt = parse_datetime(timestamp)
        px = coerce_float(price)
        if dt is None or px is None:
            continue
        points.append({"timestamp": int(dt.timestamp()), "price": px})
    return sorted(points, key=lambda item: item["timestamp"])


def _aggregate_history(points: list[dict[str, Any]], window: str | None) -> list[dict[str, Any]]:
    if not points:
        return []
    bucket_size = parse_duration_to_seconds(window) if window else None
    if not bucket_size:
        return [
            {
                "windowStart": row["timestamp"],
                "windowEnd": row["timestamp"],
                "open": row["price"],
                "high": row["price"],
                "low": row["price"],
                "close": row["price"],
                "average": row["price"],
                "count": 1,
            }
            for row in points
        ]

    buckets: dict[int, list[dict[str, Any]]] = {}
    for row in points:
        bucket_start = row["timestamp"] - (row["timestamp"] % bucket_size)
        buckets.setdefault(bucket_start, []).append(row)

    aggregated = []
    for bucket_start in sorted(buckets):
        rows = buckets[bucket_start]
        prices = [row["price"] for row in rows]
        aggregated.append(
            {
                "windowStart": bucket_start,
                "windowEnd": bucket_start + bucket_size,
                "open": rows[0]["price"],
                "high": max(prices),
                "low": min(prices),
                "close": rows[-1]["price"],
                "average": sum(prices) / len(prices),
                "count": len(rows),
            }
        )
    return aggregated


def _render_history_points(points: list[dict[str, Any]]) -> str:
    return "\n".join(f"{format_timestamp(row['timestamp'])}\t{row['price']}" for row in points)


def _render_history_ohlc(rows: list[dict[str, Any]]) -> str:
    return "\n".join(
        "\t".join(
            [
                format_timestamp(row["windowStart"]),
                format_timestamp(row["windowEnd"]),
                str(row["open"]),
                str(row["high"]),
                str(row["low"]),
                str(row["close"]),
                str(row["average"]),
                str(row["count"]),
            ]
        )
        for row in rows
    )


def _history_summary(points: list[dict[str, Any]], rows: list[dict[str, Any]]) -> dict[str, Any]:
    if not points:
        return {"points": 0, "windows": len(rows)}
    prices = [row["price"] for row in points]
    return {
        "points": len(points),
        "windows": len(rows),
        "firstTimestamp": format_timestamp(points[0]["timestamp"]),
        "lastTimestamp": format_timestamp(points[-1]["timestamp"]),
        "firstPrice": points[0]["price"],
        "lastPrice": points[-1]["price"],
        "high": max(prices),
        "low": min(prices),
        "change": points[-1]["price"] - points[0]["price"],
    }


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    client = PolymarketClient()

    if args.command in {"search", "list"}:
        filters = _resolve_market_filters(args)
        if args.command == "search" and args.query:
            markets = client.search_markets(args.query, **filters)
        else:
            markets = client.list_markets(search=getattr(args, "query", None), **filters)
        payload = []
        for market in markets:
            summary = summarize_market(market)
            if args.with_market:
                summary["market"] = market
            payload.append(summary)
        print(to_pretty_json(payload) if args.json else _render_market_table(payload, with_odds=args.with_odds))
        return 0

    if args.command == "market":
        market = summarize_market(_resolve_market(client, args))
        if args.json:
            print(to_pretty_json(market))
        else:
            lines = [
                market["question"],
                f"slug: {market['slug']}",
                f"id: {market['id']}",
                f"conditionId: {market['conditionId']}",
                f"startDate: {market.get('startDate')}",
                f"endDate: {market.get('endDate')}",
                f"liquidity: {market.get('liquidity')}",
                f"volume24hr: {market.get('volume24hr')}",
            ]
            lines.extend(f"- {row['outcome']}: {row['token_id']} @ {row['price']}" for row in market["tokens"])
            print("\n".join(lines))
        return 0

    if args.command == "book":
        token_id = _resolve_token_id(client, args)
        payload = client.get_book(token_id)
        print(
            to_pretty_json(payload)
            if args.json
            else (
                f"token_id: {token_id}\n"
                f"bids: {len(payload.get('bids', []))}\n"
                f"asks: {len(payload.get('asks', []))}\n"
                f"best_bid: {payload.get('bids', [{}])[0].get('price') if payload.get('bids') else None}\n"
                f"best_ask: {payload.get('asks', [{}])[0].get('price') if payload.get('asks') else None}"
            )
        )
        return 0

    if args.command == "midpoint":
        token_id = _resolve_token_id(client, args)
        payload = client.get_midpoint(token_id)
        print(to_pretty_json(payload) if args.json else payload.get("mid", ""))
        return 0

    if args.command == "price":
        token_id = _resolve_token_id(client, args)
        payload = client.get_last_trade_price(token_id)
        print(to_pretty_json(payload) if args.json else payload.get("price", ""))
        return 0

    if args.command == "history":
        token_id = _resolve_token_id(client, args)
        start_ts = to_unix_seconds(args.start)
        end_ts = to_unix_seconds(args.end)
        payload = client.get_price_history(
            token_id,
            interval=args.interval,
            fidelity=args.fidelity,
            start_ts=start_ts,
            end_ts=end_ts,
        )
        points = _normalize_history_points(payload)
        windows = _aggregate_history(points, args.window)
        if args.json:
            rendered: Any
            if args.format == "points":
                rendered = {"token_id": token_id, "interval": args.interval, "fidelity": args.fidelity, "history": points}
            elif args.format == "ohlc":
                rendered = {"token_id": token_id, "interval": args.interval, "fidelity": args.fidelity, "window": args.window, "ohlc": windows}
            else:
                rendered = {"token_id": token_id, "interval": args.interval, "fidelity": args.fidelity, "window": args.window, "summary": _history_summary(points, windows)}
            print(to_pretty_json(rendered))
        elif args.format == "points":
            print(_render_history_points(points))
        elif args.format == "ohlc":
            print(_render_history_ohlc(windows))
        else:
            print(to_pretty_json(_history_summary(points, windows)))
        return 0

    if args.command == "trades":
        condition_id = _resolve_condition_id(client, args)
        payload = client.get_trades(condition_id=condition_id, limit=args.limit)
        print(
            to_pretty_json(payload)
            if args.json
            else "\n".join(
                f"{row.get('timestamp')}\t{row.get('side')}\t{row.get('price')}\t{row.get('size')}\t{row.get('title') or row.get('slug')}"
                for row in payload
            )
        )
        return 0

    parser.error("unknown command")
    return 2


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
