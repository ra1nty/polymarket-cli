from __future__ import annotations

import json
from pathlib import Path
import unittest

from polymarket_clob_agent.api import ApiError, PolymarketClient


FIXTURES = Path(__file__).parent / "fixtures"


def load_fixture(name: str):
    return json.loads((FIXTURES / name).read_text())


class StubHttpClient:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    def get_json(self, url, params=None):
        self.calls.append((url, params))
        expected_url, expected_params, result = self.responses.pop(0)
        assert url == expected_url
        assert params == expected_params
        if isinstance(result, Exception):
            raise result
        return result


class PolymarketClientTests(unittest.TestCase):
    def test_get_market_slug_falls_back_to_markets_query(self):
        slug = "btc-updown-5m-1774165800"
        detail = load_fixture("market_detail.json")
        http = StubHttpClient(
            [
                (
                    f"https://gamma-api.polymarket.com/markets/slug/{slug}",
                    None,
                    ApiError("404"),
                ),
                (
                    "https://gamma-api.polymarket.com/markets",
                    {
                        "limit": 10,
                        "offset": 0,
                        "active": None,
                        "closed": None,
                        "archived": None,
                        "order": "volume_24hr",
                        "ascending": False,
                        "slug": slug,
                    },
                    [detail],
                ),
            ]
        )

        client = PolymarketClient(http=http)

        market = client.get_market(slug=slug)

        self.assertEqual(market["id"], detail["id"])
        self.assertEqual(len(http.calls), 2)

    def test_get_market_slug_falls_back_to_public_search(self):
        slug = "btc-updown-5m-1774165800"
        public_search = load_fixture("public_search.json")
        http = StubHttpClient(
            [
                (
                    f"https://gamma-api.polymarket.com/markets/slug/{slug}",
                    None,
                    ApiError("404"),
                ),
                (
                    "https://gamma-api.polymarket.com/markets",
                    {
                        "limit": 10,
                        "offset": 0,
                        "active": None,
                        "closed": None,
                        "archived": None,
                        "order": "volume_24hr",
                        "ascending": False,
                        "slug": slug,
                    },
                    [],
                ),
                (
                    "https://gamma-api.polymarket.com/public-search",
                    {
                        "q": slug,
                        "limit_per_type": 10,
                        "search_tags": False,
                        "search_profiles": False,
                        "optimized": True,
                    },
                    public_search,
                ),
            ]
        )

        client = PolymarketClient(http=http)

        market = client.get_market(slug=slug)

        self.assertEqual(market["slug"], slug)
        self.assertEqual(market["conditionId"], public_search["events"][0]["markets"][0]["conditionId"])

    def test_search_markets_prefers_public_search_for_plain_query(self):
        public_search = load_fixture("public_search.json")
        http = StubHttpClient(
            [
                (
                    "https://gamma-api.polymarket.com/public-search",
                    {
                        "q": "bitcoin",
                        "limit_per_type": 3,
                        "search_tags": False,
                        "search_profiles": False,
                        "optimized": True,
                    },
                    public_search,
                )
            ]
        )

        client = PolymarketClient(http=http)

        markets = client.search_markets("bitcoin", limit=3)

        self.assertEqual(len(markets), 1)
        self.assertEqual(markets[0]["slug"], "btc-updown-5m-1774165800")

    def test_search_markets_uses_markets_endpoint_when_advanced_filters_requested(self):
        http = StubHttpClient(
            [
                (
                    "https://gamma-api.polymarket.com/markets",
                    {
                        "limit": 2,
                        "offset": 5,
                        "active": None,
                        "closed": True,
                        "archived": True,
                        "order": "liquidity",
                        "ascending": True,
                        "search": "bitcoin",
                        "tag_id": ["100", "200"],
                        "exclude_tag_id": ["300"],
                        "related_tags": True,
                    },
                    load_fixture("market_search.json"),
                ),
            ]
        )

        client = PolymarketClient(http=http)

        markets = client.search_markets(
            "bitcoin",
            limit=2,
            offset=5,
            active=None,
            closed=True,
            archived=True,
            order="liquidity",
            ascending=True,
            tag_ids=["100", "200"],
            exclude_tag_ids=["300"],
            related_tags=True,
        )

        self.assertEqual(len(markets), 1)
        self.assertEqual(markets[0]["id"], "1669969")

    def test_search_markets_falls_back_to_public_search_and_hydrates_ranked_results(self):
        detail_a = load_fixture("market_detail.json")
        detail_b = dict(detail_a)
        detail_c = dict(detail_a)
        detail_a["id"] = "100"
        detail_a["slug"] = "iran-market-a"
        detail_a["question"] = "Will talks resume with Iran?"
        detail_a["conditionId"] = "cond-a"
        detail_a["volume24hr"] = 50
        detail_a["volume24hrClob"] = 50
        detail_a["liquidity"] = "200"
        detail_a["liquidityNum"] = 200
        detail_b["id"] = "200"
        detail_b["slug"] = "iran-market-b"
        detail_b["question"] = "Will Iran strike first?"
        detail_b["conditionId"] = "cond-b"
        detail_b["volume24hr"] = 150
        detail_b["volume24hrClob"] = 150
        detail_b["liquidity"] = "500"
        detail_b["liquidityNum"] = 500
        detail_c["id"] = "300"
        detail_c["slug"] = "iran-market-c"
        detail_c["question"] = "Will sanctions change?"
        detail_c["conditionId"] = "cond-c"
        detail_c["volume24hr"] = 100
        detail_c["volume24hrClob"] = 100
        detail_c["liquidity"] = "100"
        detail_c["liquidityNum"] = 100

        public_search = {
            "events": [
                {
                    "markets": [
                        {"slug": "iran-market-a", "question": detail_a["question"], "id": None, "conditionId": None, "volume24hr": None},
                        {"slug": "iran-market-b", "question": detail_b["question"], "id": None, "conditionId": None, "volume24hr": None},
                        {"slug": "iran-market-c", "question": detail_c["question"], "id": None, "conditionId": None, "volume24hr": None},
                    ]
                }
            ]
        }

        http = StubHttpClient(
            [
                (
                    "https://gamma-api.polymarket.com/markets",
                    {
                        "limit": 2,
                        "offset": 0,
                        "active": None,
                        "closed": None,
                        "archived": None,
                        "order": "volume_24hr",
                        "ascending": False,
                        "search": "iran",
                    },
                    ApiError("422"),
                ),
                (
                    "https://gamma-api.polymarket.com/public-search",
                    {
                        "q": "iran",
                        "limit_per_type": 25,
                        "search_tags": False,
                        "search_profiles": False,
                        "optimized": True,
                    },
                    public_search,
                ),
                (f"https://gamma-api.polymarket.com/markets/slug/{detail_a['slug']}", None, detail_a),
                (f"https://gamma-api.polymarket.com/markets/slug/{detail_b['slug']}", None, detail_b),
                (f"https://gamma-api.polymarket.com/markets/slug/{detail_c['slug']}", None, detail_c),
            ]
        )

        client = PolymarketClient(http=http)

        markets = client.search_markets(
            "iran",
            limit=2,
            active=None,
            closed=None,
            archived=None,
            order="volume24hr",
        )

        self.assertEqual([market["slug"] for market in markets], ["iran-market-b", "iran-market-c"])
        self.assertEqual(markets[0]["id"], "200")
        self.assertTrue(markets[0]["clobTokenIds"])
        self.assertEqual(markets[0]["_ranking"]["rankField"], "volume24hr")
        self.assertEqual(markets[0]["_ranking"]["rankValue"], 150.0)
        self.assertFalse(markets[0]["_ranking"]["rankingFallbackUsed"])
        self.assertFalse(markets[0]["_rankingContext"]["rankingDegraded"])

    def test_search_markets_uses_candidate_rank_when_hydrated_detail_drops_it(self):
        detail_a = load_fixture("market_detail.json")
        detail_b = dict(detail_a)
        detail_a.update(
            {
                "id": "100",
                "slug": "iran-market-a",
                "question": "Will talks resume with Iran?",
                "conditionId": "cond-a",
                "volume24hr": None,
                "volume24hrClob": None,
                "liquidity": None,
                "liquidityNum": None,
            }
        )
        detail_b.update(
            {
                "id": "200",
                "slug": "iran-market-b",
                "question": "Will Iran strike first?",
                "conditionId": "cond-b",
                "volume24hr": 90,
                "volume24hrClob": 90,
                "liquidity": "200",
                "liquidityNum": 200,
            }
        )
        public_search = {
            "events": [
                {
                    "markets": [
                        {"slug": "iran-market-a", "question": detail_a["question"], "id": None, "conditionId": None, "volume24hr": 120},
                        {"slug": "iran-market-b", "question": detail_b["question"], "id": None, "conditionId": None, "volume24hr": 90},
                    ]
                }
            ]
        }

        http = StubHttpClient(
            [
                (
                    "https://gamma-api.polymarket.com/markets",
                    {
                        "limit": 2,
                        "offset": 0,
                        "active": None,
                        "closed": None,
                        "archived": None,
                        "order": "volume_24hr",
                        "ascending": False,
                        "search": "iran",
                    },
                    ApiError("422"),
                ),
                (
                    "https://gamma-api.polymarket.com/public-search",
                    {
                        "q": "iran",
                        "limit_per_type": 25,
                        "search_tags": False,
                        "search_profiles": False,
                        "optimized": True,
                    },
                    public_search,
                ),
                (f"https://gamma-api.polymarket.com/markets/slug/{detail_a['slug']}", None, detail_a),
                (f"https://gamma-api.polymarket.com/markets/slug/{detail_b['slug']}", None, detail_b),
            ]
        )

        client = PolymarketClient(http=http)

        markets = client.search_markets(
            "iran",
            limit=2,
            active=None,
            closed=None,
            archived=None,
            order="volume24hr",
        )

        self.assertEqual([market["slug"] for market in markets], ["iran-market-a", "iran-market-b"])
        self.assertEqual(markets[0]["volume24hr"], 120)
        self.assertEqual(markets[0]["_ranking"]["rankValue"], 120.0)
        self.assertTrue(markets[0]["_ranking"]["rankingFallbackUsed"])
        self.assertEqual(markets[0]["_ranking"]["rankingSource"], "fallback")
        self.assertFalse(markets[0]["_rankingContext"]["rankingDegraded"])

    def test_search_markets_marks_unresolved_rankings_and_sorts_them_last_deterministically(self):
        detail_a = load_fixture("market_detail.json")
        detail_b = dict(detail_a)
        detail_c = dict(detail_a)
        detail_a.update(
            {
                "id": "100",
                "slug": "iran-market-a",
                "question": "Will talks resume with Iran?",
                "conditionId": "cond-a",
                "volume24hr": None,
                "volume24hrClob": None,
            }
        )
        detail_b.update(
            {
                "id": "200",
                "slug": "iran-market-b",
                "question": "Will Iran strike first?",
                "conditionId": "cond-b",
                "volume24hr": 150,
                "volume24hrClob": 150,
            }
        )
        detail_c.update(
            {
                "id": "300",
                "slug": "iran-market-c",
                "question": "Will sanctions change?",
                "conditionId": "cond-c",
                "volume24hr": 90,
                "volume24hrClob": 90,
            }
        )

        public_search = {
            "events": [
                {
                    "markets": [
                        {"slug": "iran-market-a", "question": detail_a["question"], "id": None, "conditionId": None, "volume24hr": None},
                        {"slug": "iran-market-c", "question": detail_c["question"], "id": None, "conditionId": None, "volume24hr": 90},
                        {"slug": "iran-market-b", "question": detail_b["question"], "id": None, "conditionId": None, "volume24hr": 150},
                    ]
                }
            ]
        }

        http = StubHttpClient(
            [
                (
                    "https://gamma-api.polymarket.com/markets",
                    {
                        "limit": 3,
                        "offset": 0,
                        "active": None,
                        "closed": None,
                        "archived": None,
                        "order": "volume_24hr",
                        "ascending": False,
                        "search": "iran",
                    },
                    ApiError("422"),
                ),
                (
                    "https://gamma-api.polymarket.com/public-search",
                    {
                        "q": "iran",
                        "limit_per_type": 25,
                        "search_tags": False,
                        "search_profiles": False,
                        "optimized": True,
                    },
                    public_search,
                ),
                (f"https://gamma-api.polymarket.com/markets/slug/{detail_a['slug']}", None, detail_a),
                (f"https://gamma-api.polymarket.com/markets/slug/{detail_c['slug']}", None, detail_c),
                (f"https://gamma-api.polymarket.com/markets/slug/{detail_b['slug']}", None, detail_b),
            ]
        )

        client = PolymarketClient(http=http)

        markets = client.search_markets(
            "iran",
            limit=3,
            active=None,
            closed=None,
            archived=None,
            order="volume24hr",
        )

        self.assertEqual([market["slug"] for market in markets], ["iran-market-b", "iran-market-c", "iran-market-a"])
        self.assertEqual(markets[-1]["_ranking"]["rankValue"], None)
        self.assertFalse(markets[-1]["_ranking"]["rankingResolved"])
        self.assertEqual(markets[-1]["_ranking"]["rankingSource"], "unresolved")
        self.assertTrue(markets[0]["_rankingContext"]["rankingDegraded"])
        self.assertEqual(markets[0]["_rankingContext"]["rankingIncompleteCount"], 1)
        self.assertIn("null volume24hr", markets[0]["_rankingContext"]["rankingDegradedReason"])

    def test_list_markets_applies_client_side_date_and_numeric_filters(self):
        markets = load_fixture("market_search.json")
        other = dict(markets[0])
        other["id"] = "1669970"
        other["slug"] = "btc-updown-5m-older"
        other["startDate"] = "2026-03-20T07:58:17.582157Z"
        other["endDate"] = "2026-03-20T07:55:00Z"
        other["liquidity"] = "5"
        other["liquidityNum"] = 5
        other["volume24hr"] = 10
        other["volume24hrClob"] = 10
        http = StubHttpClient(
            [
                (
                    "https://gamma-api.polymarket.com/markets",
                    {
                        "limit": 10,
                        "offset": 0,
                        "active": True,
                        "closed": False,
                        "archived": False,
                        "order": "end_date",
                        "ascending": True,
                    },
                    [markets[0], other],
                ),
            ]
        )

        client = PolymarketClient(http=http)

        result = client.list_markets(
            order="endDate",
            ascending=True,
            start_after="2026-03-21T00:00:00Z",
            end_before="2026-03-23T00:00:00Z",
            min_liquidity=100,
            min_volume24hr=1000,
        )

        self.assertEqual([market["id"] for market in result], ["1669969"])

    def test_get_price_history_passes_supported_parameters(self):
        http = StubHttpClient(
            [
                (
                    "https://clob.polymarket.com/prices-history",
                    {
                        "market": "94242206871221370391055736153305071391564432448684801902267396130896523340261",
                        "interval": "1h",
                        "fidelity": 5,
                        "startTs": 1774165200,
                        "endTs": 1774169100,
                    },
                    load_fixture("price_history.json"),
                )
            ]
        )

        client = PolymarketClient(http=http)

        payload = client.get_price_history(
            "94242206871221370391055736153305071391564432448684801902267396130896523340261",
            interval="1h",
            fidelity=5,
            start_ts=1774165200,
            end_ts=1774169100,
        )

        self.assertEqual(len(payload["history"]), 4)

    def test_get_trades_uses_market_query_param_for_condition_id(self):
        http = StubHttpClient(
            [
                (
                    "https://data-api.polymarket.com/trades",
                    {
                        "limit": 5,
                        "market": "0xba3509c3c29a52bb2f8cf8204755314a38461825e61e77e6350f5abd4b848e05",
                    },
                    load_fixture("trades.json"),
                )
            ]
        )

        client = PolymarketClient(http=http)

        trades = client.get_trades(
            condition_id="0xba3509c3c29a52bb2f8cf8204755314a38461825e61e77e6350f5abd4b848e05",
            limit=5,
        )

        self.assertEqual(len(trades), 3)
        self.assertEqual(trades[0]["slug"], "btc-updown-5m-1774165800")


if __name__ == "__main__":
    unittest.main()
