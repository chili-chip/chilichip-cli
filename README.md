# chilichip CLI

[![Python Tests](https://github.com/chili-chip/chilichip-cli/actions/workflows/test.yml/badge.svg)](https://github.com/chili-chip/chilichip-cli/actions/workflows/test.yml)
[![Docs](https://github.com/chili-chip/chilichip-cli/actions/workflows/docs.yml/badge.svg)](https://github.com/chili-chip/chilichip-cli/actions/workflows/docs.yml)

One command for the ChiliChip console: update its firmware, install games, and make your own.

```bash
pipx install https://github.com/chili-chip/chilichip-cli/releases/download/v0.8.0/chilichip-0.8.0-py3-none-any.whl

chilichip update                        # latest loader, home screen and Bitsy player
chilichip install space-cat.blit        # or a .bitsy file
chilichip new space-cat && cd space-cat
chilichip run                           # on your computer
chilichip run --console                 # on the console
chilichip                               # the TUI
```

| Command | What it does |
| ------- | ------------ |
| `chilichip` | Opens the TUI. |
| `chilichip update [--factory] [--force] [--yes]` | Updates the console firmware. Games and saves stay. |
| `chilichip install FILE... [--launch]` | Installs `.blit` and `.bitsy` files over USB. |
| `chilichip list`, `launch TITLE`, `delete TITLE` | Manages installed games. |
| `chilichip new NAME [--template game\|rpg]` | Makes a new game from the ChiliChip template. |
| `chilichip build [--console]`, `run [--console]` | Builds the game, and starts it on the desktop or the console. |
| `chilichip doctor` | Checks tools, SDKs and the console. |

**Docs: [cli.chilichip.eu](https://cli.chilichip.eu/)** (source in [docs/](docs/index.md)).

This is a fork of [32blit-tools](https://github.com/32blit/32blit-tools). It still installs the `32blit` command, which the [ChiliChip Game SDK](https://sdk.chilichip.eu/) calls to pack assets. See [The 32blit asset tools](docs/32blit.md).

## Development

```bash
cd src
python3 -m venv .venv && source .venv/bin/activate
pip install -e . pytest mock
python -m pytest
```

See [Development](docs/development.md).
