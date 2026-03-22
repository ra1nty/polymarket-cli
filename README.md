# polymarket-clob-agent

Read-only CLI for public Polymarket Gamma, CLOB, and Data API lookups.

This repo is intentionally scoped to unauthenticated public reads only. It does not place orders, manage wallets, or sign anything.

Supported public workflows:

- market discovery via `search` and `list`
- market details via `market`
- order book / midpoint / last trade price via `book`, `midpoint`, `price`
- recent public trades via `trades`
- public token price history via `history`

## Public API scope

The CLI uses only documented or already-public read-only endpoints:

- Gamma `GET /markets`
- Gamma `GET /markets/{id}` and `GET /markets/slug/{slug}`
- Gamma `GET /public-search` for plain text search fallback
- CLOB `GET /book`
- CLOB `GET /midpoint`
- CLOB `GET /last-trade-price`
- CLOB `GET /prices-history`
- Data API `GET /trades`

Behavior notes:

- `--sort`, `--ascending`, `--tag-id`, `--exclude-tag-id`, `--related-tags`, `--active-only`, `--closed-only`, and `--archived` are passed through to public Gamma market listing where supported.
- Date windows and numeric thresholds are applied client-side after fetch so the CLI stays read-only and does not invent undocumented Gamma parameters.
- Plain `search <query>` prefers Gamma public search for discoverability.
- Ranked keyword search is resilient: if `GET /markets?search=...` fails for a sort/filter combination, the CLI falls back to public search candidates, hydrates market detail, then filters and sorts client-side.
- Ranked keyword search resolves `volume24hr` / `liquidity` from hydrated market detail first and falls back to the originating search candidate when detail leaves those fields null.
- If some matching candidates still have null rank fields after fallback resolution, the CLI sorts those rows last deterministically and marks the returned set as degraded instead of silently claiming a clean top-by-rank result.
- `--hydrate`, `--with-odds`, and `--with-market` make search/list results agent-friendly without leaving the public read-only API surface.

## Setup

### Preferred: `uv tool install --editable .`

For a local checkout, the best fit is an editable uv tool install: it gives you the real `pmkt` CLI entrypoint while keeping the source tree live.

```bash
uv tool install --editable .
pmkt --help
```

If uv's tool bin directory is not on your `PATH` yet:

```bash
uv tool update-shell
# or run the installed executable directly
"$(uv tool dir --bin)"/pmkt --help
```

For one-off usage without installing the tool:

```bash
uvx --from . pmkt --help
```

In sandboxed environments, point uv's cache and XDG paths into the workspace:

```bash
XDG_BIN_HOME="$PWD/.local-bin" \
XDG_DATA_HOME="$PWD/.local-share" \
UV_CACHE_DIR="$PWD/.uv-cache" \
uv tool install --editable .
```

### Secondary: `uv run`

If you specifically want project-mode execution instead of the tools workflow:

```bash
uv run pmkt --help
```

### Secondary: editable install with `pip`

```bash
python3 -m pip install -e .
pmkt --help
```

### Direct module execution

```bash
PYTHONPATH=. python3 -m polymarket_clob_agent --help
```

## Usage

### Market discovery

Search active markets by default:

```bash
pmkt search bitcoin --limit 5
pmkt search election --sort liquidity --json
pmkt search iran --sort volume24hr --active-only --with-odds --limit 5
```

List with explicit status and sort controls:

```bash
pmkt list --active-only --sort volume24hr --limit 20
pmkt list --closed-only --sort endDate --ascending --limit 20
pmkt list --archived --sort liquidity --ascending
```

Tag and date filtering:

```bash
pmkt list --tag-id 100381 --related-tags --limit 25
pmkt search soccer --exclude-tag-id 123 --end-before 2026-06-01T00:00:00Z
pmkt list --min-liquidity 10000 --min-volume24hr 5000
```

Hydration and one-shot ranked odds workflows:

```bash
pmkt search iran --sort volume24hr --active-only --with-odds --limit 5
pmkt search iran --sort liquidity --all --hydrate --json
pmkt search iran --sort volume24hr --active-only --with-market --json
```

Hydration notes:

- `--hydrate` resolves matching search/list rows to full market detail before local ranking/filtering.
- `--with-odds` implies hydration and includes current outcome prices in text and JSON output.
- `--with-market` implies hydration and embeds the resolved raw market payload in JSON output.
- Ranked search/list JSON includes `rankField`, `rankValue`, `rankingResolved`, `rankingSource`, `rankingFallbackUsed`, and set-level degradation fields so downstream agents can tell whether a top-N result is clean or only best-effort.

Supported sort values:

- `volume24hr`
- `volume`
- `liquidity`
- `startDate`
- `endDate`
- `competitive`
- `closedTime`

### Market details

```bash
pmkt market --slug btc-updown-5m-1774165800
pmkt market --id 1669969 --json
```

### Order book and spot pricing

Use a token id directly:

```bash
pmkt book --token-id 94242206871221370391055736153305071391564432448684801902267396130896523340261
pmkt midpoint --token-id 94242206871221370391055736153305071391564432448684801902267396130896523340261
pmkt price --token-id 94242206871221370391055736153305071391564432448684801902267396130896523340261
```

Or resolve from a market plus outcome:

```bash
pmkt book --slug btc-updown-5m-1774165800 --outcome Down
pmkt midpoint --id 1669969 --outcome Up
pmkt price --slug btc-updown-5m-1774165800
```

### Price history

Fetch raw public history points:

```bash
pmkt history --token-id 94242206871221370391055736153305071391564432448684801902267396130896523340261 \
  --interval 1h \
  --fidelity 5 \
  --start 2026-03-22T00:00:00Z \
  --end 2026-03-22T12:00:00Z
```

Resolve token ids from a market and aggregate locally for agent consumption:

```bash
pmkt history --slug btc-updown-5m-1774165800 --outcome Down --interval 1h --window 60 --format ohlc
pmkt history --slug btc-updown-5m-1774165800 --window 6h --format summary --json
```

Supported history intervals are the public CLOB values:

- `max`
- `all`
- `1m`
- `1h`
- `6h`
- `1d`
- `1w`

History notes:

- `--interval`, `--fidelity`, `--start`, and `--end` map directly to the public `prices-history` endpoint.
- `--window` is local aggregation on top of raw history output and accepts either bare minute counts like `60` or explicit durations like `15m`, `1h`, `1d`, `1w`.
- `--format points` prints normalized `timestamp<TAB>price`.
- `--format ohlc` prints `windowStart`, `windowEnd`, `open`, `high`, `low`, `close`, `average`, `count`.
- `--format summary` prints a compact JSON summary.

### Public trades

```bash
pmkt trades --slug btc-updown-5m-1774165800 --limit 20
pmkt trades --condition-id 0xba3509c3c29a52bb2f8cf8204755314a38461825e61e77e6350f5abd4b848e05 --json
```

## Agent-facing behavior

The CLI is intended to be stable and scriptable:

- text output is tabular / line-oriented by default
- `--json` is available on every command
- market selectors are explicit: `--slug`, `--id`, `--token-id`, `--condition-id`
- outcome resolution is deterministic: if no `--outcome` is given, the first market token is used
- hydrated market search/list JSON includes normalized `liquidity`, `volume24hr`, `conditionId`, per-outcome `odds` / `tokens`, and ranking-quality metadata for ranked workflows

## Development

Run tests with `uv`:

```bash
PYTHONPATH=. uv run --no-project python -m unittest discover -s tests -v
```

Preferred `uv` smoke checks:

```bash
uvx --from . pmkt --help
uvx --from . pmkt search --help
uvx --from . pmkt search iran --limit 5 --sort volume24hr --active-only --with-odds --json
```

Equivalent plain Python command:

```bash
PYTHONPATH=. python3 -m unittest discover -s tests -v
```

## Tested in this repo

The fixture-backed test suite covers:

- market search fallback behavior
- ranked keyword fallback hydration when Gamma search fails
- advanced market filter and sort wiring
- slug resolution
- token resolution from outcomes
- public trades lookups
- price history retrieval and aggregation formatting

The tests do not require live network access.
