# polymarket-cli

Read-only CLI for public Polymarket Gamma, CLOB, and Data API lookups.

This repo stays intentionally narrow: public, unauthenticated reads only. It does not place orders, manage wallets, sign anything, or depend on private APIs.

The published Python distribution is `polymarket-cli`, the import package is `polymarket_cli`, and the command stays `pmkt`.

## What `pmkt` covers

- market discovery via `search` and `list`
- market detail lookup via `market`
- order book and spot pricing via `book`, `midpoint`, and `price`
- recent public trades via `trades`
- public token price history via `history`

The CLI uses only public Polymarket endpoints:

- Gamma `GET /markets`
- Gamma `GET /markets/{id}` and `GET /markets/slug/{slug}`
- Gamma `GET /public-search`
- CLOB `GET /book`
- CLOB `GET /midpoint`
- CLOB `GET /last-trade-price`
- CLOB `GET /prices-history`
- Data API `GET /trades`

## Install

### Default for a local checkout

Use `uv tool install --editable .` for the real `pmkt` entrypoint while keeping the checkout live:

```bash
uv tool install --editable .
pmkt --help
```

If uv's tool bin directory is not on your `PATH` yet:

```bash
uv tool update-shell
# or run the binary directly
"$(uv tool dir --bin)"/pmkt --help
```

For one-off execution without installing:

```bash
uvx --from . pmkt --help
```

### Default for a published release

```bash
uv tool install polymarket-cli
pmkt --help
```

### Secondary project-mode execution

```bash
uv run pmkt --help
```

## Usage

### Market discovery

```bash
pmkt search bitcoin --limit 5
pmkt search election --sort liquidity --json
pmkt search iran --sort volume24hr --active-only --with-odds --limit 5

pmkt list --active-only --sort volume24hr --limit 20
pmkt list --closed-only --sort endDate --ascending --limit 20
pmkt list --tag-id 100381 --related-tags --limit 25
pmkt list --min-liquidity 10000 --min-volume24hr 5000
```

Useful options:

- `--json` is available on every command.
- `--hydrate` resolves search/list rows to full market detail before local ranking or filtering.
- `--with-odds` implies hydration and includes current outcome prices.
- `--with-market` implies hydration and embeds the resolved market payload in JSON output.
- Supported sort values are `volume24hr`, `volume`, `liquidity`, `startDate`, `endDate`, `competitive`, and `closedTime`.

### Market details

```bash
pmkt market --slug btc-updown-5m-1774165800
pmkt market --id 1669969 --json
```

### Order book and spot pricing

```bash
pmkt book --token-id 94242206871221370391055736153305071391564432448684801902267396130896523340261
pmkt midpoint --token-id 94242206871221370391055736153305071391564432448684801902267396130896523340261
pmkt price --slug btc-updown-5m-1774165800
pmkt book --slug btc-updown-5m-1774165800 --outcome Down
```

### Price history

```bash
pmkt history --token-id 94242206871221370391055736153305071391564432448684801902267396130896523340261 \
  --interval 1h \
  --fidelity 5 \
  --start 2026-03-22T00:00:00Z \
  --end 2026-03-22T12:00:00Z

pmkt history --slug btc-updown-5m-1774165800 --outcome Down --interval 1h --window 60 --format ohlc
pmkt history --slug btc-updown-5m-1774165800 --window 6h --format summary --json
```

Supported history intervals:

- `max`
- `all`
- `1m`
- `1h`
- `6h`
- `1d`
- `1w`

### Public trades

```bash
pmkt trades --slug btc-updown-5m-1774165800 --limit 20
pmkt trades --condition-id 0xba3509c3c29a52bb2f8cf8204755314a38461825e61e77e6350f5abd4b848e05 --json
```

## CLI behavior

- Text output is line-oriented by default.
- `--json` is available everywhere for automation.
- Market selectors are explicit: `--slug`, `--id`, `--token-id`, `--condition-id`.
- If no `--outcome` is given for token-resolving commands, the first market token is used.
- Ranked search/list JSON includes ranking metadata so downstream tools can detect fallback or degraded result sets.

## Development

Run tests:

```bash
uv run --no-project python -m unittest discover -s tests -v
```

Build artifacts:

```bash
uv build
```

Quick smoke checks:

```bash
uvx --from . pmkt --help
uvx --from . pmkt search --help
```

The fixture-backed test suite does not require live network access.

## Release publishing

GitHub Actions handles publishing to TestPyPI and PyPI with trusted publishing (OIDC). No API tokens or repository secrets are required in this repo.

Required GitHub-side setup:

1. Configure a trusted publisher for this repository in TestPyPI.
2. Configure a trusted publisher for this repository in PyPI.
3. If you want manual approval before production release, protect the GitHub `pypi` environment.

Workflow behavior:

- CI runs on pushes and pull requests.
- TestPyPI publishing runs on version tags like `v1.2.3-rc1` and by manual dispatch.
- PyPI publishing runs on GitHub release publication and by manual dispatch.
