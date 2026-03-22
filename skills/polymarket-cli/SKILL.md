---
name: polymarket-cli
description: Use the polymarket-cli command for read-only Polymarket market discovery, market/token resolution, price snapshots, history, trades, and JSON-safe scripting.
---

# Using `polymarket-cli`

Use this skill when an agent needs public, read-only Polymarket data from this package without calling Gamma, CLOB, or Data API endpoints directly.

Install the published CLI:

```bash
uv tool install polymarket-cli
polymarket-cli --help
```

For one-off execution without installing:

```bash
uvx polymarket-cli --help
```

## When to use `polymarket-cli`

- Discover markets by keyword, liquidity, volume, tags, or date windows.
- Resolve a market `slug` or `id` into a `conditionId` or outcome `token_id`.
- Pull spot pricing with `book`, `midpoint`, or `price`.
- Pull recent public trades for a market condition.
- Pull token price history and locally aggregate it into OHLC or summaries.
- Produce scriptable JSON output for another tool or agent step.

## Command patterns

```bash
polymarket-cli search bitcoin --limit 5
polymarket-cli list --active-only --sort liquidity --min-liquidity 10000
polymarket-cli market --slug <market-slug> --json
polymarket-cli book --slug <market-slug> --outcome Yes
polymarket-cli history --slug <market-slug> --window 6h --format summary --json
polymarket-cli trades --condition-id <condition-id> --json
```

## Working rules

- Prefer `polymarket-cli` in docs, prompts, and automation.
- Prefer `--json` whenever another step will parse the result.
- Use explicit selectors: `--slug`, `--id`, `--token-id`, `--condition-id`.
- Keep usage read-only. This package does not place orders, manage wallets, or use private/authenticated APIs.
