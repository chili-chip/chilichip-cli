# Commands

Every command has `--help`. Errors print one line starting with `Error:` and exit with code 1.

| Command | Options | What it does |
| ------- | ------- | ------------ |
| `chilichip` | `--version`, `--help` | Opens the [TUI](tui.md). |
| [`chilichip update`](update.md) | `--factory`, `--force`, `--yes` | Installs the latest loader, home screen and Bitsy player. |
| [`chilichip install FILE...`](games.md#install) | `--launch` | Installs `.blit` games and `.bitsy` files. |
| [`chilichip list`](games.md#list) | | Lists the loader version and installed games. |
| [`chilichip launch TITLE`](games.md#launch) | | Starts an installed game. |
| [`chilichip delete TITLE`](games.md#delete) | `--yes` | Deletes an installed game. Saves stay. |
| [`chilichip new NAME`](projects.md#new) | `--template game\|rpg`, `--author` | Makes a new game from a template. |
| [`chilichip build`](projects.md#build) | `--desktop` (default), `--console` | Builds the game in the current folder. |
| [`chilichip run`](projects.md#run) | `--desktop` (default), `--console` | Builds and starts the game. |
| [`chilichip doctor`](doctor.md) | | Checks tools, SDKs and the console. |

## Environment variables

| Variable | Effect |
| -------- | ------ |
| `GITHUB_TOKEN` | Sent to the GitHub API by `update`, to avoid the rate limit of 60 requests an hour. Any token works; it needs no scopes. |

## Files

| Path | What |
| ---- | ---- |
| `<app dir>/cache/` | Downloaded firmware, see [Where the downloads go](update.md#where-the-downloads-go). |
| `out/build/linux/`, `out/build/vgc-blit/` | Build folders inside a game, made by `build` and `run`. |

## Exit codes

| Code | Meaning |
| ---- | ------- |
| 0 | Done. |
| 1 | An error with a message, or `doctor` found something missing. |
| 2 | Wrong options (from the command line parser). |
