# New, build and run

Three commands take you from nothing to a game running on the console:

```bash
chilichip new space-cat
cd space-cat
chilichip run              # on your computer
chilichip run --console    # on the console
```

![The TUI's New project tab](assets/screenshots/tui-new.svg){ .tui }

## New

```bash
chilichip new NAME [--template game|rpg] [--author NAME]
```

1. Downloads the latest [game template](https://github.com/chili-chip/game-template) (or the [RPG template](https://github.com/chili-chip/rpg-template)) into a folder called `NAME`, without the template's git history.
2. Renames it: `project(NAME ...)` in `CMakeLists.txt`, and `title` and `author` in `metadata.yml`. The author is `git config user.name` unless you pass `--author`.
3. Starts a fresh git repository with one commit.
4. Checks that `32blit-sdk`, `pico-sdk` and `pico-extras` are next to the game, and offers to download the missing ones from [chili-chip](https://github.com/chili-chip).

```console
$ chilichip new space-cat
Created /home/ada/projects/space-cat
Missing next to your game: pico-sdk, pico-extras
Download them now? [Y/n]: y
Next: cd space-cat && chilichip run
```

| Template | What you get |
| -------- | ------------ |
| `game` (default) | A small working game with CMake presets for desktop and console, CI, and a save example. |
| `rpg` | An RPG starter with tile map assets. It has no CMake presets, so `chilichip` passes the same settings itself. |

The name becomes the CMake target and the title on the home screen, so it can have up to 24 letters, digits, `-` and `_`, and starts with a letter. Change the title later in `metadata.yml`.

## Build

```bash
chilichip build             # for this computer (default)
chilichip build --console   # a .blit for the console
```

Run it anywhere inside the game folder. It wraps the template's CMake presets:

| Flag | Preset | Output |
| ---- | ------ | ------ |
| `--desktop` | `linux` | `out/build/linux/NAME.elf` |
| `--console` | `vgc-blit` | `out/build/vgc-blit/NAME.blit` |

The first build configures the folder (`cmake --preset ...`); later builds only run `cmake --build`. CMake's own output is shown as it runs. To start over, delete `out/build/<preset>`.

The same presets work in VS Code's CMake Tools, so the editor and `chilichip` share build folders.

## Run

```bash
chilichip run               # build, then start the game on this computer
chilichip run --console     # build, install over USB, then start it on the console
```

`run --console` checks the `.blit` before uploading, like [`install`](games.md#checks-before-uploading) does, and uses the console's API version from its loader.

![The TUI's Build and run tab](assets/screenshots/tui-build.svg){ .tui }

## Supported systems

| System | Desktop builds | Console builds |
| ------ | -------------- | -------------- |
| Linux | yes | yes |
| macOS | yes | yes |
| Windows (WSL) | yes | yes |
| Windows (native) | no, use Visual Studio as the [SDK docs](https://sdk.chilichip.eu/setup/visual-studio/) describe | no |
