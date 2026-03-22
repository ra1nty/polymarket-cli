# polymarket-cli

Read-only CLI for public Polymarket Gamma, CLOB, and Data API lookups.

This package stays intentionally narrow: public, unauthenticated reads only. It does not place orders, manage wallets, sign anything, or depend on private APIs.

The published Python distribution is `polymarket-cli`, the import package is `polymarket_cli`, and the command is `polymarket-cli`.

## What It Covers

- Market discovery via `search` and `list`
- Market detail lookup via `market`
- Order book and spot pricing via `book`, `midpoint`, and `price`
- Recent public trades via `trades`
- Public token price history via `history`

## Install

```bash
uv tool install polymarket-cli
polymarket-cli --help
```

For one-off execution:

```bash
uvx polymarket-cli --help
```

If your `uv` tool bin directory is not on `PATH`, either run `uv tool update-shell` or call the binary directly from `$(uv tool dir --bin)`.

## Claude Code And Codex

In Claude Code or Codex, install the published CLI in the agent shell environment:

```bash
uv tool install polymarket-cli
polymarket-cli search bitcoin --limit 5
```

For ephemeral runs inside those environments:

```bash
uvx polymarket-cli market --slug <market-slug> --json
```

If you want the agent to treat this repo as a reusable skill bundle, use the bundled skill at `skills/polymarket-cli/`.

## Usage

```bash
polymarket-cli search bitcoin --limit 5
polymarket-cli list --active-only --sort volume24hr --limit 20
polymarket-cli market --slug btc-updown-5m-1774165800
polymarket-cli book --slug btc-updown-5m-1774165800 --outcome Down
polymarket-cli price --slug btc-updown-5m-1774165800
polymarket-cli history --slug btc-updown-5m-1774165800 --window 6h --format summary --json
polymarket-cli trades --slug btc-updown-5m-1774165800 --limit 20
```

Useful flags:

- `--json` is available on every command.
- `--hydrate` resolves search/list rows to full market detail before local ranking or filtering.
- `--with-odds` implies hydration and includes current outcome prices.
- `--with-market` implies hydration and embeds the resolved market payload in JSON output.
- Market selectors are explicit: `--slug`, `--id`, `--token-id`, `--condition-id`.

Supported history intervals: `max`, `all`, `1m`, `1h`, `6h`, `1d`, `1w`.
