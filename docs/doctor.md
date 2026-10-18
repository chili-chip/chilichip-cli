# Doctor

```bash
chilichip doctor
```

Checks everything the build needs and the console. Each line is `ok` with what was found, or `no` with the command that fixes it.

| Check | Needed for | Looks for |
| ----- | ---------- | --------- |
| CMake | all builds | `cmake` |
| Git | `new` | `git` |
| C++ compiler | desktop builds | `g++`, `clang++` or `c++` |
| SDL2 | desktop builds | `sdl2-config` (installed with the SDL2 development package) |
| Arm toolchain | console builds | `arm-none-eabi-gcc` |
| 32blit tool | all builds | `32blit` (CMake calls it to pack assets) |
| 32blit-sdk | all builds | a `32blit-sdk` folder next to your game |
| pico-sdk, pico-extras | console builds | folders next to your game |
| Console | `install`, `run --console`, `update` | a USB device with ID `cafe:4003` |

Run it inside a game folder to check the SDKs next to that game, or in the folder that holds your games.

`doctor` exits with code 1 when a tool or SDK is missing, so scripts can use it. A missing console doesn't count, because desktop builds don't need one.
