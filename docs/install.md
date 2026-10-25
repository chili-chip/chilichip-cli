# Install

`chilichip` needs Python 3.10 or newer. Install it with [pipx](https://pipx.pypa.io/), which keeps it in its own environment and puts the `chilichip` and `32blit` commands on your `PATH`.

=== "Ubuntu / Debian / WSL"

    ```bash
    sudo apt install pipx git
    pipx ensurepath
    pipx install git+https://github.com/chili-chip/chilichip-cli#subdirectory=src
    ```

=== "macOS"

    ```bash
    brew install pipx git
    pipx ensurepath
    pipx install git+https://github.com/chili-chip/chilichip-cli#subdirectory=src
    ```

=== "Windows"

    Install [Python](https://www.python.org/downloads/) and [Git](https://git-scm.com/download/win), then in PowerShell:

    ```powershell
    py -m pip install --user pipx
    py -m pipx ensurepath
    pipx install git+https://github.com/chili-chip/chilichip-cli#subdirectory=src
    ```

    Firmware updates and game installs work on Windows. To build games for the console, use WSL as the [SDK docs](https://sdk.chilichip.eu/getting-started/install/) describe.

Open a new terminal, then check it works:

```console
$ chilichip --version
chilichip, version 0.8.0
```

Update it later with `pipx upgrade chilichip`.

!!! note "Already using the 32blit tools?"
    `chilichip` includes the `32blit` command. Uninstall the old one first (`pip uninstall 32blit`, or delete the virtual environment you made for it), so only one `32blit` is on your `PATH`.

## USB access on Linux

The console shows up as a serial port, for example `/dev/ttyACM0`. On most Linux systems only the `dialout` group can open serial ports. Add yourself once, then log out and back in:

```bash
sudo usermod -aG dialout $USER
```

Without this, commands that talk to the console fail with `Cannot open /dev/ttyACM0: Permission denied`.

## Check your setup

Run [`chilichip doctor`](doctor.md). It lists every tool and SDK the build needs and says how to install what is missing:

```console
$ chilichip doctor
ok  CMake          /usr/bin/cmake
ok  Git            /usr/bin/git
ok  C++ compiler   /usr/bin/g++
ok  SDL2           /usr/bin/sdl2-config
no  Arm toolchain  sudo apt install gcc-arm-none-eabi libnewlib-arm-none-eabi libstdc++-arm-none-eabi-newlib, or brew install --cask gcc-arm-embedded
ok  32blit tool    /home/ada/.local/bin/32blit
ok  32blit-sdk     /home/ada/projects/32blit-sdk
no  pico-sdk       git clone --recurse-submodules https://github.com/chili-chip/pico-sdk /home/ada/projects/pico-sdk
no  pico-extras    git clone https://github.com/chili-chip/pico-extras /home/ada/projects/pico-extras
ok  Console        /dev/ttyACM0
```

You only need the console tools (Arm toolchain, `pico-sdk`, `pico-extras`) to build games for the console. Updating the firmware and installing games need nothing but `chilichip` and a USB cable.

## Folder layout

Game projects expect the SDKs next to them, as in the SDK's [Install the tools](https://sdk.chilichip.eu/getting-started/install/) page. `chilichip new` offers to download whatever is missing:

```
projects/
├── 32blit-sdk/      # ChiliChip Game SDK
├── pico-sdk/        # console builds only
├── pico-extras/     # console builds only
└── space-cat/       # your game, made with chilichip new
```
