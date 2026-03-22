# polymarket-cli

Read-only CLI for public Polymarket Gamma, CLOB, and Data API lookups.

This package stays intentionally narrow: public, unauthenticated reads only. It does not place orders, manage wallets, sign anything, or depend on private APIs.

The published Pypi package is `polymarket-cli`. 

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

The published package pins a bundled CA root store via `certifi`, so HTTPS works consistently in environments where `uv` or Homebrew Python points at an incomplete local OpenSSL trust store. If you already manage trust with `SSL_CERT_FILE` or `SSL_CERT_DIR`, the CLI respects those overrides.

For one-off execution:

```bash
uvx polymarket-cli --help
```

If your `uv` tool bin directory is not on `PATH`, either run `uv tool update-shell` or call the binary directly from `$(uv tool dir --bin)`.

## Agent Skill Installation

Install the packaged skill with `npx skills`:

### OpenClaw

```bash
npx skills add ra1nty/polymarket-cli -a openclaw
```

### Claude Code

```bash
npx skills add ra1nty/polymarket-cli -a claude-code
```

After installation, use the public command surface in agent prompts and automation:

```bash
polymarket-cli search bitcoin --limit 5
polymarket-cli market --slug <market-slug> --json
```

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
