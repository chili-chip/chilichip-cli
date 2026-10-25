# Development

The code is in `src/`:

| Path | What |
| ---- | ---- |
| `src/chilichip/console.py` | Finding the console, the `.blit` header, the version command, installing, BOOTSEL. |
| `src/chilichip/firmware.py` | GitHub releases, downloads, the update plan and the update itself. |
| `src/chilichip/project.py` | `new`, `build`, `run`, `doctor`. |
| `src/chilichip/cli.py` | The `chilichip` command. |
| `src/chilichip/tui.py` | The TUI, built with [Textual](https://textual.textualize.io/). |
| `src/ttblit/` | The upstream 32blit tools and the `32blit` command. |

The CLI and the TUI are thin: both call the functions in `console.py`, `firmware.py` and `project.py`.

## Set up

```bash
git clone https://github.com/chili-chip/chilichip-cli
cd chilichip-cli/src
python3 -m venv .venv
source .venv/bin/activate
pip install -e . pytest mock
```

## Tests

```bash
cd src
python -m pytest
```

| Test file | Covers |
| --------- | ------ |
| `tests/test_chilichip_console.py` | Console detection, `.blit` checks, the serial commands against a fake port, BOOTSEL drive detection |
| `tests/test_chilichip_firmware.py` | Version compare, release assets, sha256 checks, the update plan and flow |
| `tests/test_chilichip_project.py` | Renaming the template, presets, builds, `doctor` |
| `tests/test_chilichip_cli.py` | The commands and the TUI starting up |
| `tests/test_*.py` (others) | The upstream 32blit tools |

The serial tests use `tests/fakes.py`, a `Console` that reads and writes byte buffers. CI also runs `chilichip new` and `chilichip build --desktop` on the real template.

Things that need a console are checked by hand: `update` from an older release, `update --factory`, the hold-X fallback, `install`, `run --console`.

## Docs

```bash
pip install -r docs/requirements.txt
mkdocs serve
```

The TUI screenshots are made from the app itself with a fake console:

```bash
python scripts/screenshots.py
```

## Releases

1. Set the new version in `src/ttblit/__init__.py` and add its section at the top of `src/CHANGELOG.txt`.
2. Update the `pipx install` file name in `README.md`, `docs/index.md` and `docs/install.md`.
3. Merge to `main`, then tag it and push the tag:

    ```bash
    git tag v0.8.1
    git push origin v0.8.1
    ```

The [Release workflow](https://github.com/chili-chip/chilichip-cli/actions/workflows/release.yml) checks that the tag matches the version, builds the wheel and sdist, and creates the GitHub release with the changelog section as its notes. If the release was already made on GitHub's Releases page, it adds the files to it and keeps its notes.

## Upstream

This is a fork of [32blit/32blit-tools](https://github.com/32blit/32blit-tools). Keep changes under `src/ttblit/` small and generic, so they can go upstream.
