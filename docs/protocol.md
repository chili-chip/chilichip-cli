# USB serial protocol

The console's loader is a USB device with a serial port (CDC) and a drive (MSC). Its USB ID is `cafe:4003` and its name is "ChiliChip Console". `chilichip` and `32blit` talk to the serial port with these commands. The loader side is `32blit-pico/usb.cpp` in the [SDK](https://github.com/chili-chip/32blit-sdk).

Every command starts with `32BL` and a 4 character name. The loader runs a command only when the byte after that header arrives, so commands with nothing more to send end with a NUL byte. Strings end with a NUL byte. Numbers are little-endian.

| Command | Sent | Reply | Used by |
| ------- | ---- | ----- | ------- |
| `32BLVERS` | NUL | `32BLVERS`, the loader version (for example `v1.0.1`) and NUL, then API major and minor as `uint16` | `update`, `list`, `install` |
| `32BL__LS` | NUL | per game: offset `uint32`, size `uint32`, `BLITMETA` metadata; then `FF FF FF FF` | `list`, `update` |
| `32BLPROG` | file name, NUL, size in decimal, NUL, file data | `32BL__OK` and the flash block as `uint16`, or nothing on error | `install` (`.blit`) |
| `32BLSAVE` | path, NUL, size in decimal, NUL, file data | `32BL__OK`, or nothing on error | `install` (`.bitsy`) |
| `32BLLNCH` | path (`flash:/<block>` or a file), NUL | nothing | `launch`, `install --launch` |
| `32BLERSE` | offset `uint32` | nothing | `delete` |

Loaders older than `32BLVERS` answer with the text line `got: 32BLVERS` and CRLF. `chilichip` reads and drops that line, so it can't end up in front of the next reply, and treats the loader as out of date. It waits one second for an answer.

## Restarting into BOOTSEL

The loader is built with `PICO_STDIO_USB_ENABLE_RESET_VIA_BAUD_RATE`. Opening its serial port at 1200 baud restarts the RP2350 into its USB bootloader, which shows up as a drive named `RP2350`. `chilichip update` uses this to flash the loader without you holding a button.

## The `.blit` header

`chilichip` reads the first 28 bytes of a `.blit` to catch files the console would refuse:

| Offset | Size | Field |
| ------ | ---- | ----- |
| 0 | 4 | `BLIT` |
| 16 | 4 | end of the game code; the low 25 bits are the offset of the `BLITMETA` block |
| 20 | 1 | device: 0 and 1 are 32Blit, 2 is RP2040, 3 is RP2350 (the ChiliChip console) |
| 24 | 2 | API major |
| 26 | 2 | API minor |

The console runs a game when the device is 3, the API major matches the loader's, and the API minor is not newer than the loader's.

## Try it from Python

```python
import serial, struct

with serial.Serial('/dev/ttyACM0', timeout=1) as port:
    port.write(b'32BLVERS\0')
    assert port.read(8) == b'32BLVERS'
    version = port.read_until(b'\0')[:-1].decode()
    major, minor = struct.unpack('<HH', port.read(4))
    print(version, f'API {major}.{minor}')
```
