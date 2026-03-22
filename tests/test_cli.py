from __future__ import annotations

import io
import json
from pathlib import Path
import unittest
from contextlib import redirect_stdout
from unittest.mock import patch

from polymarket_cli import cli
from polymarket_cli.formatting import parse_duration_to_seconds


FIXTURES = Path(__file__).parent / "fixtures"


def load_fixture(name: str):
    return json.loads((FIXTURES / name).read_text())


class FakeClient:
    instances = []

    def __init__(self):
        self.market = load_fixture("market_detail.json")
        self.book = load_fixture("book.json")
        self.midpoint = load_fixture("midpoint.json")
        self.last_trade_price = load_fixture("last_trade_price.json")
        self.trades = load_fixture("trades.json")
        self.search = load_fixture("market_search.json")
        self.history = load_fixture("price_history.json")
        self.calls = []
        type(self).instances.append(self)

    def search_markets(self, query, **kwargs):
        self.calls.append(("search_markets", query, kwargs))
        return self.search[: kwargs.get("limit", 10)]

    def list_markets(self, **kwargs):
        self.calls.append(("list_markets", kwargs))
        return self.search[: kwargs.get("limit", 10)]

    def get_market(self, *, slug=None, market_id=None):
        self.calls.append(("get_market", slug, market_id))
        return self.market

    def get_book(self, token_id):
        self.calls.append(("get_book", token_id))
        return self.book

    def get_midpoint(self, token_id):
        self.calls.append(("get_midpoint", token_id))
        return self.midpoint

    def get_last_trade_price(self, token_id):
        self.calls.append(("get_last_trade_price", token_id))
        return self.last_trade_price

    def get_price_history(self, token_id, *, interval="1d", fidelity=60, start_ts=None, end_ts=None):
        self.calls.append(("get_price_history", token_id, interval, fidelity, start_ts, end_ts))
        return self.history

    def get_trades(self, *, market=None, condition_id=None, limit=20):
        self.calls.append(("get_trades", market, condition_id, limit))
        return self.trades[:limit]


class CliTests(unittest.TestCase):
    def setUp(self):
        FakeClient.instances.clear()

    def run_cli(self, argv):
        buf = io.StringIO()
        with patch("polymarket_cli.cli.PolymarketClient", FakeClient):
            with redirect_stdout(buf):
                rc = cli.main(argv)
        client = FakeClient.instances[-1]
        return rc, buf.getvalue(), client

    def test_search_uses_search_markets_for_query(self):
        rc, output, client = self.run_cli(["search", "bitcoin", "--json"])

        self.assertEqual(rc, 0)
        self.assertIn("btc-updown-5m-1774165800", output)
        self.assertEqual(
            client.calls[0],
            (
                "search_markets",
                "bitcoin",
                {
                    "limit": 10,
                    "offset": 0,
                    "active": True,
                    "closed": False,
                    "archived": False,
                    "order": "volume24hr",
                    "ascending": False,
                    "tag_ids": None,
                    "exclude_tag_ids": None,
                    "related_tags": False,
                    "start_after": None,
                    "start_before": None,
                    "end_after": None,
                    "end_before": None,
                    "min_liquidity": None,
                    "max_liquidity": None,
                    "min_volume24hr": None,
                    "max_volume24hr": None,
                    "hydrate": False,
                },
            ),
        )

    def test_list_passes_advanced_filtering_flags(self):
        rc, output, client = self.run_cli(
            [
                "list",
                "--limit",
                "5",
                "--offset",
                "10",
                "--closed-only",
                "--archived",
                "--ascending",
                "--sort",
                "liquidity",
                "--tag-id",
                "100381",
                "--exclude-tag-id",
                "999",
                "--related-tags",
                "--end-before",
                "2026-03-23T00:00:00Z",
                "--min-liquidity",
                "1000",
            ]
        )

        self.assertEqual(rc, 0)
        self.assertIn("btc-updown-5m-1774165800", output)
        self.assertEqual(
            client.calls[0],
            (
                "list_markets",
                {
                    "search": None,
                    "limit": 5,
                    "offset": 10,
                    "active": None,
                    "closed": True,
                    "archived": True,
                    "order": "liquidity",
                    "ascending": True,
                    "tag_ids": ["100381"],
                    "exclude_tag_ids": ["999"],
                    "related_tags": True,
                    "start_after": None,
                    "start_before": None,
                    "end_after": None,
                    "end_before": "2026-03-23T00:00:00Z",
                    "min_liquidity": 1000.0,
                    "max_liquidity": None,
                    "min_volume24hr": None,
                    "max_volume24hr": None,
                    "hydrate": False,
                },
            ),
        )

    def test_search_with_odds_implies_hydration_and_renders_prices(self):
        rc, output, client = self.run_cli(["search", "iran", "--limit", "1", "--with-odds"])

        self.assertEqual(rc, 0)
        self.assertIn("Up=0.005", output)
        self.assertEqual(
            client.calls[0],
            (
                "search_markets",
                "iran",
                {
                    "limit": 1,
                    "offset": 0,
                    "active": True,
                    "closed": False,
                    "archived": False,
                    "order": "volume24hr",
                    "ascending": False,
                    "tag_ids": None,
                    "exclude_tag_ids": None,
                    "related_tags": False,
                    "start_after": None,
                    "start_before": None,
                    "end_after": None,
                    "end_before": None,
                    "min_liquidity": None,
                    "max_liquidity": None,
                    "min_volume24hr": None,
                    "max_volume24hr": None,
                    "hydrate": True,
                },
            ),
        )

    def test_search_with_market_embeds_raw_market_in_json(self):
        rc, output, client = self.run_cli(["search", "iran", "--limit", "1", "--with-market", "--json"])

        self.assertEqual(rc, 0)
        payload = json.loads(output)
        self.assertEqual(payload[0]["market"]["id"], "1669969")
        self.assertEqual(client.calls[0][2]["hydrate"], True)

    def test_search_json_includes_ranking_metadata(self):
        market = load_fixture("market_search.json")[0]
        search_row = dict(market)
        search_row["_ranking"] = {
            "rankField": "volume24hr",
            "rankValue": 70934.07902500001,
            "rankingResolved": True,
            "rankingSource": "market",
            "rankingFallbackUsed": False,
        }
        search_row["_rankingContext"] = {
            "rankingDegraded": True,
            "rankingIncompleteCount": 2,
            "rankingDegradedReason": "2 matching candidate(s) had null volume24hr after fallback resolution",
        }
        buf = io.StringIO()

        class RankingClient(FakeClient):
            def __init__(self):
                super().__init__()
                self.search = [search_row]

        with patch("polymarket_cli.cli.PolymarketClient", RankingClient):
            with redirect_stdout(buf):
                rc = cli.main(["search", "iran", "--json"])
        client = RankingClient.instances[-1]

        self.assertEqual(rc, 0)
        payload = json.loads(buf.getvalue())
        self.assertEqual(payload[0]["rankField"], "volume24hr")
        self.assertEqual(payload[0]["rankValue"], 70934.07902500001)
        self.assertTrue(payload[0]["rankingResolved"])
        self.assertFalse(payload[0]["rankingFallbackUsed"])
        self.assertTrue(payload[0]["rankingDegraded"])
        self.assertEqual(payload[0]["rankingIncompleteCount"], 2)
        self.assertIn("null volume24hr", payload[0]["rankingDegradedReason"])
        self.assertEqual(client.calls[0][0], "search_markets")

    def test_market_renders_market_details(self):
        rc, output, client = self.run_cli(["market", "--slug", "btc-updown-5m-1774165800"])

        self.assertEqual(rc, 0)
        self.assertIn("Bitcoin Up or Down", output)
        self.assertIn("conditionId: 0xba3509c3c29a52bb2f8cf8204755314a38461825e61e77e6350f5abd4b848e05", output)
        self.assertEqual(client.calls[0], ("get_market", "btc-updown-5m-1774165800", None))

    def test_book_resolves_token_by_outcome(self):
        rc, output, client = self.run_cli(["book", "--slug", "btc-updown-5m-1774165800", "--outcome", "Down"])

        self.assertEqual(rc, 0)
        self.assertIn("token_id: 22943400237250229318795315882775337816951160275867284205243766113690886285726", output)
        self.assertEqual(client.calls[-1], ("get_book", "22943400237250229318795315882775337816951160275867284205243766113690886285726"))

    def test_price_accepts_token_id_directly(self):
        rc, output, client = self.run_cli(
            ["price", "--token-id", "94242206871221370391055736153305071391564432448684801902267396130896523340261"]
        )

        self.assertEqual(rc, 0)
        self.assertEqual(output.strip(), "0.001")
        self.assertEqual(
            client.calls[0],
            ("get_last_trade_price", "94242206871221370391055736153305071391564432448684801902267396130896523340261"),
        )

    def test_history_supports_time_window_and_summary(self):
        rc, output, client = self.run_cli(
            [
                "history",
                "--token-id",
                "94242206871221370391055736153305071391564432448684801902267396130896523340261",
                "--interval",
                "1h",
                "--fidelity",
                "5",
                "--start",
                "2026-03-22T07:00:00Z",
                "--end",
                "2026-03-22T08:05:00Z",
                "--window",
                "60",
                "--format",
                "summary",
            ]
        )

        self.assertEqual(rc, 0)
        self.assertIn('"windows": 2', output)
        self.assertEqual(
            client.calls[0],
            (
                "get_price_history",
                "94242206871221370391055736153305071391564432448684801902267396130896523340261",
                "1h",
                5,
                1774162800,
                1774166700,
            ),
        )

    def test_trades_resolves_condition_id_from_market(self):
        rc, output, client = self.run_cli(["trades", "--slug", "btc-updown-5m-1774165800", "--limit", "2"])

        self.assertEqual(rc, 0)
        self.assertIn("BUY", output)
        self.assertIn("Bitcoin Up or Down", output)
        self.assertEqual(client.calls[0], ("get_market", "btc-updown-5m-1774165800", None))
        self.assertEqual(client.calls[1], ("get_trades", None, "0xba3509c3c29a52bb2f8cf8204755314a38461825e61e77e6350f5abd4b848e05", 2))

    def test_trades_requires_condition_or_market_selector(self):
        with patch("polymarket_cli.cli.PolymarketClient", FakeClient):
            with self.assertRaises(SystemExit) as ctx:
                cli.main(["trades"])

        self.assertIn("Provide --condition-id or a market selector", str(ctx.exception))

    def test_history_window_parser_accepts_bare_minutes(self):
        self.assertEqual(parse_duration_to_seconds("60"), 3600)
        self.assertEqual(parse_duration_to_seconds("15m"), 900)

    def test_history_window_error_lists_supported_formats(self):
        with self.assertRaises(SystemExit) as ctx, patch("sys.stderr", new_callable=io.StringIO) as stderr:
            cli.main(["history", "--token-id", "123", "--window", "hourly"])

        self.assertEqual(ctx.exception.code, 2)
        self.assertIn("window must be a positive minute count like 60", stderr.getvalue())


if __name__ == "__main__":
    unittest.main()
