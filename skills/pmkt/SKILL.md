---
name: pmkt
description: Use the pmkt CLI for read-only Polymarket market discovery, market/token resolution, price snapshots, history, trades, and JSON-safe scripting.
---

# Using `pmkt` Effectively

Use this skill when an agent needs public, read-only Polymarket data from this repo without calling Gamma/CLOB/Data APIs directly.

Default to the uv tools workflow for this repo:

```bash
uv tool install --editable .
pmkt --help
```

For the published package:

```bash
uv tool install polymarket-cli
pmkt --help
```

For one-off execution without installing:

```bash
uvx --from . pmkt --help
```

## When to use `pmkt`

- Discover markets by keyword, liquidity, volume, tags, or date windows.
- Resolve a market `slug` or `id` into a `conditionId` or outcome `token_id`.
- Pull spot pricing with `book`, `midpoint`, or `price`.
- Pull recent public trades for a market condition.
- Pull token price history and locally aggregate it into OHLC or summaries.
- Produce scriptable JSON output for another tool or agent step.

## Command patterns

```bash
# discovery
pmkt search bitcoin --limit 5
pmkt list --active-only --sort liquidity --min-liquidity 10000
pmkt search iran --sort volume24hr --active-only --with-odds --limit 5
pmkt search iran --sort volume24hr --all --hydrate --json

# market -> identifiers
pmkt market --slug <market-slug> --json
pmkt trades --slug <market-slug> --limit 20

# market -> token resolution
pmkt book --slug <market-slug> --outcome Yes
pmkt midpoint --id <market-id> --outcome No
pmkt price --slug <market-slug>

# history
pmkt history --token-id <token-id> --interval 1h --fidelity 5
pmkt history --slug <market-slug> --outcome Yes --window 60 --format ohlc
pmkt history --slug <market-slug> --window 6h --format summary --json

# scriptable output
pmkt search election --limit 10 --json
pmkt market --slug <market-slug> --json
pmkt trades --condition-id <condition-id> --json
```

## Working rules

- Prefer the installed `pmkt` executable from `uv tool install --editable .` when working in this checkout.
- Prefer `uv tool install polymarket-cli` when you only need the released CLI rather than a live checkout.
- Use `uvx --from . pmkt ...` for ephemeral runs where installation would add unnecessary state.
- Prefer `--json` whenever another step will parse the result.
- Use `search ... --with-odds` for a one-shot ranked market list with live outcome prices.
- Use `search/list ... --hydrate` when public search rows are missing ids, condition ids, liquidity, volume, or token metadata.
- Use `search/list ... --with-market --json` when a downstream step needs the resolved raw market payload.
- Use explicit selectors: `--slug`, `--id`, `--token-id`, `--condition-id`.
- For `book`, `midpoint`, `price`, and `history`, `--outcome` resolves the outcome token from the selected market. If omitted, `pmkt` uses the first market token.
- `history --window` is local aggregation only. It accepts bare minute counts like `60` or duration strings like `15m`, `1h`, `1d`, `1w`.
- `trades` uses a market `conditionId`. If you only have a slug or id, let `pmkt trades --slug ...` resolve it.
- Keep usage read-only. This repo does not place orders, manage wallets, or use private/authenticated APIs.
