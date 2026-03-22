from __future__ import annotations

import json
import urllib.parse
import urllib.request
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Iterable

from .formatting import coerce_float, parse_datetime

DEFAULT_HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; polymarket-cli/0.1)",
    "Accept": "application/json",
}

GAMMA_ORDER_MAP = {
    "volume24hr": "volume_24hr",
    "volume_24hr": "volume_24hr",
    "volume": "volume",
    "liquidity": "liquidity",
    "startDate": "start_date",
    "start_date": "start_date",
    "endDate": "end_date",
    "end_date": "end_date",
    "competitive": "competitive",
    "closedTime": "closed_time",
    "closed_time": "closed_time",
}

HISTORY_INTERVALS = {"max", "all", "1m", "1h", "6h", "1d", "1w"}
RANK_FIELD_ALIASES = {
    "liquidity": ("liquidityNum", "liquidity"),
    "volume_24hr": ("volume24hrClob", "volume24hr"),
    "volume": ("volumeClob", "volume"),
    "start_date": ("startDate", "startDateIso"),
    "end_date": ("endDate", "endDateIso"),
    "competitive": ("competitive",),
    "closed_time": ("closedTime",),
}
DISPLAY_ORDER_MAP = {
    "volume_24hr": "volume24hr",
    "start_date": "startDate",
    "end_date": "endDate",
    "closed_time": "closedTime",
}


class ApiError(RuntimeError):
    pass


@dataclass
class HttpClient:
    timeout: float = 20.0
    headers: dict[str, str] | None = None

    def __post_init__(self) -> None:
        merged = dict(DEFAULT_HEADERS)
        if self.headers:
            merged.update(self.headers)
        self.headers = merged

    def _iter_param_pairs(self, params: dict[str, Any]) -> Iterable[tuple[str, str]]:
        for key, value in params.items():
            if value is None:
                continue
            if isinstance(value, (list, tuple)):
                for item in value:
                    if item is None:
                        continue
                    if isinstance(item, bool):
                        item = str(item).lower()
                    yield key, str(item)
                continue
            if isinstance(value, bool):
                value = str(value).lower()
            yield key, str(value)

    def get_json(self, url: str, params: dict[str, Any] | None = None) -> Any:
        if params:
            query = urllib.parse.urlencode(list(self._iter_param_pairs(params)), doseq=True)
            sep = "&" if "?" in url else "?"
            url = f"{url}{sep}{query}"
        req = urllib.request.Request(url, headers=self.headers)
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                return json.load(resp)
        except Exception as exc:  # pragma: no cover - exercised through tests with stubs
            raise ApiError(f"GET {url} failed: {exc}") from exc


class PolymarketClient:
    def __init__(self, http: HttpClient | None = None) -> None:
        self.http = http or HttpClient()
        self.gamma_base = "https://gamma-api.polymarket.com"
        self.clob_base = "https://clob.polymarket.com"
        self.data_base = "https://data-api.polymarket.com"

    def list_markets(
        self,
        *,
        limit: int = 10,
        offset: int = 0,
        active: bool | None = True,
        closed: bool | None = False,
        archived: bool | None = False,
        search: str | None = None,
        slug: str | None = None,
        order: str = "volume24hr",
        ascending: bool = False,
        tag_ids: list[str] | None = None,
        exclude_tag_ids: list[str] | None = None,
        related_tags: bool = False,
        start_after: str | None = None,
        start_before: str | None = None,
        end_after: str | None = None,
        end_before: str | None = None,
        min_liquidity: float | None = None,
        max_liquidity: float | None = None,
        min_volume24hr: float | None = None,
        max_volume24hr: float | None = None,
        hydrate: bool = False,
    ) -> list[dict[str, Any]]:
        gamma_order = self._normalize_market_order(order)
        params: dict[str, Any] = {
            "limit": limit,
            "offset": offset,
            "active": active,
            "closed": closed,
            "archived": archived,
            "order": gamma_order,
            "ascending": ascending,
        }
        if search:
            params["search"] = search
        if slug:
            params["slug"] = slug
        if tag_ids:
            params["tag_id"] = tag_ids
        if exclude_tag_ids:
            params["exclude_tag_id"] = exclude_tag_ids
        if related_tags:
            params["related_tags"] = True

        data = self.http.get_json(f"{self.gamma_base}/markets", params)
        markets = list(data)
        if hydrate:
            markets = self._hydrate_markets(markets, order=gamma_order, include_tokens=True)
        filtered = self._filter_markets(
            markets,
            active=None,
            closed=None,
            archived=None,
            tag_ids=None,
            exclude_tag_ids=None,
            order=gamma_order,
            ascending=ascending,
            start_after=start_after,
            start_before=start_before,
            end_after=end_after,
            end_before=end_before,
            min_liquidity=min_liquidity,
            max_liquidity=max_liquidity,
            min_volume24hr=min_volume24hr,
            max_volume24hr=max_volume24hr,
        )
        return self._annotate_rankings(filtered, order=gamma_order)

    def get_market(self, *, slug: str | None = None, market_id: str | None = None) -> dict[str, Any]:
        if bool(slug) == bool(market_id):
            raise ValueError("Provide exactly one of slug or market_id")
        if slug:
            return self.get_market_by_slug(slug)
        return dict(self.http.get_json(f"{self.gamma_base}/markets/{market_id}"))

    def find_market(self, query: str, *, limit: int = 10) -> list[dict[str, Any]]:
        return self.list_markets(limit=limit, active=None, closed=None, archived=None, search=query)

    def search_markets(
        self,
        query: str,
        *,
        limit: int = 10,
        offset: int = 0,
        active: bool | None = True,
        closed: bool | None = False,
        archived: bool | None = False,
        order: str = "volume24hr",
        ascending: bool = False,
        tag_ids: list[str] | None = None,
        exclude_tag_ids: list[str] | None = None,
        related_tags: bool = False,
        start_after: str | None = None,
        start_before: str | None = None,
        end_after: str | None = None,
        end_before: str | None = None,
        min_liquidity: float | None = None,
        max_liquidity: float | None = None,
        min_volume24hr: float | None = None,
        max_volume24hr: float | None = None,
        hydrate: bool = False,
    ) -> list[dict[str, Any]]:
        if not query:
            return []

        gamma_order = self._normalize_market_order(order)
        requires_ranked_search = any(
            value
            for value in (
                offset,
                tag_ids,
                exclude_tag_ids,
                related_tags,
                start_after,
                start_before,
                end_after,
                end_before,
                min_liquidity,
                max_liquidity,
                min_volume24hr,
                max_volume24hr,
                ascending,
                archived is not False,
                active is not True,
                closed is not False,
                gamma_order != "volume_24hr",
                hydrate,
            )
        )
        if requires_ranked_search:
            try:
                return self.list_markets(
                    limit=limit,
                    offset=offset,
                    active=active,
                    closed=closed,
                    archived=archived,
                    search=query,
                    order=order,
                    ascending=ascending,
                    tag_ids=tag_ids,
                    exclude_tag_ids=exclude_tag_ids,
                related_tags=related_tags,
                start_after=start_after,
                start_before=start_before,
                end_after=end_after,
                end_before=end_before,
                min_liquidity=min_liquidity,
                max_liquidity=max_liquidity,
                min_volume24hr=min_volume24hr,
                max_volume24hr=max_volume24hr,
                hydrate=hydrate,
            )
            except ApiError:
                pass

        candidate_limit = self._search_candidate_limit(limit=limit, offset=offset, hydrate=hydrate or requires_ranked_search)
        markets = self._search_public_markets(query, limit=candidate_limit)
        if not markets:
            return []

        if hydrate or requires_ranked_search:
            markets = self._hydrate_markets(markets, order=gamma_order, include_tokens=True)

        filtered = self._filter_markets(
            markets,
            active=active,
            closed=closed,
            archived=archived,
            tag_ids=tag_ids,
            exclude_tag_ids=exclude_tag_ids,
            order=gamma_order,
            ascending=ascending,
            start_after=start_after,
            start_before=start_before,
            end_after=end_after,
            end_before=end_before,
            min_liquidity=min_liquidity,
            max_liquidity=max_liquidity,
            min_volume24hr=min_volume24hr,
            max_volume24hr=max_volume24hr,
        )
        return self._annotate_rankings(filtered, order=gamma_order)[offset : offset + limit]

    def get_market_by_slug(self, slug: str) -> dict[str, Any]:
        quoted_slug = urllib.parse.quote(slug)
        try:
            return dict(self.http.get_json(f"{self.gamma_base}/markets/slug/{quoted_slug}"))
        except ApiError:
            pass

        exact = self.list_markets(
            limit=10,
            active=None,
            closed=None,
            archived=None,
            slug=slug,
        )
        match = self._select_market_match(exact, slug)
        if match:
            return match

        fallback = self.search_markets(slug, limit=10)
        match = self._select_market_match(fallback, slug)
        if match:
            return match
        raise ApiError(f"Market not found for slug: {slug}")

    def _search_public_markets(self, query: str, *, limit: int) -> list[dict[str, Any]]:
        public_search = None
        try:
            public_search = self.http.get_json(
                f"{self.gamma_base}/public-search",
                {
                    "q": query,
                    "limit_per_type": limit,
                    "search_tags": False,
                    "search_profiles": False,
                    "optimized": True,
                },
            )
        except ApiError:
            pass

        markets = self._extract_public_search_markets(public_search)
        if markets:
            return markets

        try:
            return self.list_markets(
                limit=limit,
                offset=0,
                active=None,
                closed=None,
                archived=None,
                search=query,
                order="volume24hr",
            )
        except ApiError:
            return []

    def _extract_public_search_markets(self, payload: Any) -> list[dict[str, Any]]:
        events = payload.get("events") if isinstance(payload, dict) else []
        markets: list[dict[str, Any]] = []
        for event in events or []:
            for market in event.get("markets") or []:
                if isinstance(market, dict):
                    markets.append(market)
        return markets

    def _search_candidate_limit(self, *, limit: int, offset: int, hydrate: bool) -> int:
        minimum = offset + limit
        if not hydrate:
            return max(minimum, 1)
        return max(minimum * 5, 25)

    def _hydrate_markets(self, markets: list[dict[str, Any]], *, order: str, include_tokens: bool) -> list[dict[str, Any]]:
        hydrated = []
        for market in markets:
            candidate = dict(market)
            if self._market_needs_hydration(candidate, order=order, include_tokens=include_tokens):
                refreshed = self._hydrate_market(candidate)
                if refreshed is not None:
                    candidate = self._merge_market_ranking_fields(candidate, refreshed)
            hydrated.append(candidate)
        return hydrated

    def _merge_market_ranking_fields(self, candidate: dict[str, Any], refreshed: dict[str, Any]) -> dict[str, Any]:
        merged = dict(refreshed)
        for field_names in RANK_FIELD_ALIASES.values():
            for field_name in field_names:
                if merged.get(field_name) in (None, "") and candidate.get(field_name) not in (None, ""):
                    merged[field_name] = candidate[field_name]
        return merged

    def _hydrate_market(self, market: dict[str, Any]) -> dict[str, Any] | None:
        slug = market.get("slug")
        market_id = market.get("id")
        try:
            if slug:
                return self.get_market_by_slug(str(slug))
            if market_id:
                return self.get_market(market_id=str(market_id))
        except ApiError:
            return None
        return None

    def _market_needs_hydration(self, market: dict[str, Any], *, order: str, include_tokens: bool) -> bool:
        if not market.get("id") or not market.get("conditionId"):
            return True
        if include_tokens and not market.get("clobTokenIds"):
            return True
        if order == "liquidity" and coerce_float(market.get("liquidityNum") or market.get("liquidity")) is None:
            return True
        if order == "volume_24hr" and coerce_float(market.get("volume24hrClob") or market.get("volume24hr")) is None:
            return True
        if order == "volume" and coerce_float(market.get("volumeClob") or market.get("volume")) is None:
            return True
        if order == "start_date" and parse_datetime(market.get("startDate") or market.get("startDateIso")) is None:
            return True
        if order == "end_date" and parse_datetime(market.get("endDate") or market.get("endDateIso")) is None:
            return True
        return False

    def _select_market_match(self, markets: list[dict[str, Any]], slug: str) -> dict[str, Any] | None:
        if not markets:
            return None

        normalized = slug.strip().lower()
        for market in markets:
            if str(market.get("slug", "")).strip().lower() == normalized:
                return dict(market)

        for market in markets:
            event_slug = ""
            events = market.get("events")
            if isinstance(events, list) and events:
                first_event = events[0]
                if isinstance(first_event, dict):
                    event_slug = str(first_event.get("slug", "")).strip().lower()
            if event_slug == normalized:
                return dict(market)

        return dict(markets[0])

    def get_book(self, token_id: str) -> dict[str, Any]:
        return dict(self.http.get_json(f"{self.clob_base}/book", {"token_id": token_id}))

    def get_midpoint(self, token_id: str) -> dict[str, Any]:
        return dict(self.http.get_json(f"{self.clob_base}/midpoint", {"token_id": token_id}))

    def get_last_trade_price(self, token_id: str) -> dict[str, Any]:
        return dict(self.http.get_json(f"{self.clob_base}/last-trade-price", {"token_id": token_id}))

    def get_price_history(
        self,
        token_id: str,
        *,
        interval: str = "1d",
        fidelity: int = 60,
        start_ts: int | None = None,
        end_ts: int | None = None,
    ) -> dict[str, Any]:
        if interval not in HISTORY_INTERVALS:
            raise ValueError(f"Unsupported interval: {interval}")
        params: dict[str, Any] = {"market": token_id, "interval": interval, "fidelity": fidelity}
        if start_ts is not None:
            params["startTs"] = start_ts
        if end_ts is not None:
            params["endTs"] = end_ts
        return dict(self.http.get_json(f"{self.clob_base}/prices-history", params))

    def get_trades(self, *, market: str | None = None, condition_id: str | None = None, limit: int = 20) -> list[dict[str, Any]]:
        params = {"limit": limit}
        market_filter = condition_id or market
        if market_filter:
            params["market"] = market_filter
        data = self.http.get_json(f"{self.data_base}/trades", params)
        return list(data)

    def _normalize_market_order(self, order: str) -> str:
        try:
            return GAMMA_ORDER_MAP[order]
        except KeyError as exc:
            valid = ", ".join(sorted(GAMMA_ORDER_MAP))
            raise ValueError(f"Unsupported market sort field: {order}. Choose from: {valid}") from exc

    def _filter_markets(
        self,
        markets: list[dict[str, Any]],
        *,
        active: bool | None,
        closed: bool | None,
        archived: bool | None,
        tag_ids: list[str] | None,
        exclude_tag_ids: list[str] | None,
        order: str,
        ascending: bool,
        start_after: str | None,
        start_before: str | None,
        end_after: str | None,
        end_before: str | None,
        min_liquidity: float | None,
        max_liquidity: float | None,
        min_volume24hr: float | None,
        max_volume24hr: float | None,
    ) -> list[dict[str, Any]]:
        start_after_dt = parse_datetime(start_after)
        start_before_dt = parse_datetime(start_before)
        end_after_dt = parse_datetime(end_after)
        end_before_dt = parse_datetime(end_before)
        filtered = []
        for market in markets:
            if active is not None and bool(market.get("active")) != active:
                continue
            if closed is not None and bool(market.get("closed")) != closed:
                continue
            if archived is not None and bool(market.get("archived")) != archived:
                continue
            market_tag_ids = self._market_tag_ids(market)
            has_tag_metadata = self._market_has_tag_metadata(market)
            if tag_ids and has_tag_metadata and not all(tag_id in market_tag_ids for tag_id in tag_ids):
                continue
            if exclude_tag_ids and has_tag_metadata and any(tag_id in market_tag_ids for tag_id in exclude_tag_ids):
                continue
            start_dt = parse_datetime(market.get("startDate") or market.get("startDateIso"))
            end_dt = parse_datetime(market.get("endDate") or market.get("endDateIso"))
            liquidity = coerce_float(market.get("liquidityNum") or market.get("liquidity"))
            volume24hr = coerce_float(market.get("volume24hrClob") or market.get("volume24hr"))
            if start_after_dt and (start_dt is None or start_dt < start_after_dt):
                continue
            if start_before_dt and (start_dt is None or start_dt > start_before_dt):
                continue
            if end_after_dt and (end_dt is None or end_dt < end_after_dt):
                continue
            if end_before_dt and (end_dt is None or end_dt > end_before_dt):
                continue
            if min_liquidity is not None and (liquidity is None or liquidity < min_liquidity):
                continue
            if max_liquidity is not None and (liquidity is None or liquidity > max_liquidity):
                continue
            if min_volume24hr is not None and (volume24hr is None or volume24hr < min_volume24hr):
                continue
            if max_volume24hr is not None and (volume24hr is None or volume24hr > max_volume24hr):
                continue
            filtered.append(market)

        sort_key = self._market_sort_key(order, ascending)
        return sorted(filtered, key=sort_key)

    def _market_tag_ids(self, market: dict[str, Any]) -> set[str]:
        values: set[str] = set()
        self._collect_tag_ids(values, market.get("tags"))
        events = market.get("events")
        if isinstance(events, list):
            for event in events:
                if isinstance(event, dict):
                    self._collect_tag_ids(values, event.get("tags"))
        return values

    def _market_has_tag_metadata(self, market: dict[str, Any]) -> bool:
        if market.get("tags") is not None:
            return True
        events = market.get("events")
        if isinstance(events, list):
            for event in events:
                if isinstance(event, dict) and event.get("tags") is not None:
                    return True
        return False

    def _collect_tag_ids(self, values: set[str], payload: Any) -> None:
        if isinstance(payload, dict):
            for key in ("id", "tagId"):
                value = payload.get(key)
                if value not in (None, ""):
                    values.add(str(value))
            return
        if isinstance(payload, list):
            for item in payload:
                self._collect_tag_ids(values, item)
            return
        if payload not in (None, ""):
            values.add(str(payload))

    def _market_sort_key(self, order: str, ascending: bool):
        def key(market: dict[str, Any]) -> tuple[int, float, str, str, str]:
            value = self._market_order_value(market, order)
            if isinstance(value, datetime):
                sort_value = value.timestamp()
            elif value is None:
                sort_value = 0.0
            else:
                sort_value = float(value)
            if value is not None and not ascending:
                sort_value *= -1
            return (
                0 if value is not None else 1,
                sort_value,
                str(market.get("slug") or ""),
                str(market.get("id") or ""),
                str(market.get("question") or ""),
            )

        return key

    def _market_order_value(self, market: dict[str, Any], order: str) -> Any:
        if order == "liquidity":
            return coerce_float(market.get("liquidityNum") or market.get("liquidity"))
        if order in {"volume_24hr", "volume"}:
            field = "volume24hrClob" if order == "volume_24hr" else "volumeClob"
            fallback = "volume24hr" if order == "volume_24hr" else "volume"
            return coerce_float(market.get(field) or market.get(fallback))
        if order == "start_date":
            return parse_datetime(market.get("startDate") or market.get("startDateIso"))
        if order == "end_date":
            return parse_datetime(market.get("endDate") or market.get("endDateIso"))
        if order == "competitive":
            return coerce_float(market.get("competitive"))
        if order == "closed_time":
            return parse_datetime(market.get("closedTime"))
        return None

    def _annotate_rankings(self, markets: list[dict[str, Any]], *, order: str) -> list[dict[str, Any]]:
        unresolved = 0
        annotated = []
        rank_field = DISPLAY_ORDER_MAP.get(order, order)
        for market in markets:
            annotated_market = dict(market)
            rank_value = self._market_order_value(annotated_market, order)
            ranking_resolved = rank_value is not None
            if not ranking_resolved:
                unresolved += 1
            annotated_market["_ranking"] = {
                "rankField": rank_field,
                "rankValue": self._serialize_rank_value(rank_value),
                "rankingResolved": ranking_resolved,
                "rankingSource": self._ranking_source(annotated_market, order, ranking_resolved),
                "rankingFallbackUsed": self._ranking_fallback_used(annotated_market, order),
            }
            annotated.append(annotated_market)

        degraded = unresolved > 0
        reason = None
        if degraded:
            reason = f"{unresolved} matching candidate(s) had null {rank_field} after fallback resolution"
        for market in annotated:
            market["_rankingContext"] = {
                "rankingDegraded": degraded,
                "rankingIncompleteCount": unresolved,
                "rankingDegradedReason": reason,
            }
        return annotated

    def _ranking_source(self, market: dict[str, Any], order: str, ranking_resolved: bool) -> str:
        if not ranking_resolved:
            return "unresolved"
        return "fallback" if self._ranking_fallback_used(market, order) else "market"

    def _ranking_fallback_used(self, market: dict[str, Any], order: str) -> bool:
        field_names = RANK_FIELD_ALIASES.get(order, ())
        if not field_names:
            return False
        primary = field_names[0]
        if market.get(primary) not in (None, ""):
            return False
        return any(market.get(field_name) not in (None, "") for field_name in field_names[1:])

    def _serialize_rank_value(self, value: Any) -> Any:
        if isinstance(value, datetime):
            return value.isoformat().replace("+00:00", "Z")
        return value
