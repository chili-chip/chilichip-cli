# Install and manage games

All of these find the console by its USB ID, `cafe:4003`. You don't need to pass a port.

## Install

```bash
chilichip install space-cat.blit
chilichip install cat-adventure.bitsy
chilichip install *.blit --launch
```

| File | Where it goes |
| ---- | ------------- |
| `.blit` | Into flash, on the home screen. A game with the same title and author is replaced and keeps its saves. |
| `.bitsy` | The `bitsy-games` folder on the console's drive. The Bitsy player lists it on the home screen. |

`--launch` starts the last file once it is installed.

### Checks before uploading

`install` reads the `.blit` header first and refuses files the console would reject:

| Message | Cause | Fix |
| ------- | ----- | --- |
| `game.blit is not a ChiliChip game: it was built for 32Blit` | built for another device (`device_id` is not 3, RP2350) | build with the `vgc-blit` preset from a clean build folder: `rm -rf out/build/vgc-blit && chilichip build --console` |
| `game.blit needs a system update: it uses API 0.7, the console has 0.6` | built with a newer SDK than the console's loader | run `chilichip update` |
| `game.blit is not a .blit file.` | the file is damaged or something else | rebuild it |

The console checks the same things. Catching them on your computer gives a clearer message.

## List

```console
$ chilichip list
Loader: v1.0.1
  4  ChiliChip OS              v1.0.0      chilichip         142 KB
  7  Bitsy                     v0.2.0      TeriyakiGod       393 KB
 14  Doom Fire                 v1.0.0      andreban          50 KB
```

The columns are the flash block (64 KB each), title, version, author and size.

## Launch

```bash
chilichip launch "Doom Fire"
```

Starts an installed game by its title. Case doesn't matter.

## Delete

```bash
chilichip delete "Doom Fire"
```

Asks first; `--yes` skips the question. Saves stay on the console's drive, in `.blit/<title>/`, so installing the game again brings them back.

## The drive still works

You can still copy `.blit` files onto the `CHILICHIP` drive, as the [SDK docs](https://sdk.chilichip.eu/getting-started/build-console/#install-it) describe. `chilichip install` is faster for testing, because you don't have to eject the drive.
