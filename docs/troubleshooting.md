# Troubleshooting

| Message or problem | Cause | Fix |
| ------------------ | ----- | --- |
| `No console found.` | The console is off, the cable only charges, or the loader isn't running. | Switch the console on and use a data cable. Check that a "ChiliChip Console" USB device appears (`lsusb` shows `cafe:4003`). |
| `Cannot open /dev/ttyACM0: Permission denied` | Linux only lets the `dialout` group open serial ports. | `sudo usermod -aG dialout $USER`, then log out and in. |
| `No RP2350 drive found.` | The console didn't restart into BOOTSEL, or the drive didn't mount. | Switch the console off, hold **X**, switch it on, and run `chilichip update` again. On Linux without automount, mount the drive under `/media/$USER/`. |
| `The console did not come back.` | The loader was flashed but the console didn't restart. | Switch it off and on. Run `chilichip update` again to finish. |
| `... the download is damaged (sha256 does not match)` | A broken download or a proxy that changed the file. | Run the command again. The bad file is already deleted. |
| `Cannot reach GitHub ...` | No internet, or GitHub's rate limit. | Check your connection. Set `GITHUB_TOKEN` for a higher limit. |
| `... is not a ChiliChip game: it was built for ...` | The `.blit` was built for another device. | Delete the build folder and build with `chilichip build --console`. |
| `... needs a system update` | The game uses a newer SDK than the console. | `chilichip update` |
| `Failed to save/flash ...` | The loader refused the file: not enough space, or the drive is busy. | Delete a game, eject the `CHILICHIP` drive on your computer, and try again. |
| `This is not a game project.` | `build` or `run` outside a game folder. | `cd` into the folder with `CMakeLists.txt` and `metadata.yml`. |
| `cmake is not installed.` (or another tool) | A build tool is missing. | Run `chilichip doctor` and follow the fixes it prints. |
| `Could not find a package configuration file provided by "32BLIT"` | `32blit-sdk` isn't next to your game. | `git clone https://github.com/chili-chip/32blit-sdk` in the folder that holds your game. |
| Two `32blit` commands | The old `32blit` package is still installed. | `pip uninstall 32blit`, or remove the old virtual environment from your `PATH`. |

Still stuck? Open an issue on [chili-chip/chilichip-cli](https://github.com/chili-chip/chilichip-cli/issues) with the full output. Add `-v` to `32blit` commands for more detail.
