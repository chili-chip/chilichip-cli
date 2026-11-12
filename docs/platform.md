# Games from Chili Platform

Link this computer to your [Chili Platform](https://platform.chilichip.eu) account once. Then install the games in your library on the console over USB. The console needs no Wi-Fi: your computer downloads the game and copies it over the cable.

## Link this computer

```console
$ chilichip login
On any device, open https://platform.chilichip.eu/link
and enter the code: BCDF-GHJK
Or open: https://platform.chilichip.eu/link?code=BCDF-GHJK
Waiting for you to approve it...
Linked as "chilichip CLI on ada-laptop". Next: chilichip library
```

Open the link on your phone or computer, sign in, check the code and press **Link this device**. Your account needs a verified email address. You never type your password into the terminal.

* `--name "Ada's laptop"` sets how this computer shows in your account. The default is `chilichip CLI on <computer name>`.
* The code works for 15 minutes. If it runs out, run `chilichip login` again.
* Linking follows the OAuth 2.0 Device Authorization Grant ([RFC 8628](https://www.rfc-editor.org/rfc/rfc8628)), the same flow the platform offers to consoles. The platform gives this computer a device token that only reads your library and downloads its games. It can't buy, sell or change anything.

The token is saved in `<app dir>/platform.json`, readable only by you (see [Where the downloads go](update.md#where-the-downloads-go) for `<app dir>`).

## See your library

```console
$ chilichip library
   12  Cat Adventure             ada               Bitsy       18 KB
   15  Drum Night                kacper            Chili Beat  6 KB
   21  Lighthouse Keeper         pawel             Bitsy       40 KB
Install one with: chilichip install --from-platform "<title>"
```

Your library is the games you bought and the games you released yourself, the same as the **Library** page on the website. The columns are the game's id, title, author, kind and size.

## Install from the library

```bash
chilichip install --from-platform "Cat Adventure"
chilichip install --from-platform 12 21
chilichip install --from-platform --all
```

Name games by title (case doesn't matter) or by id. `--all` installs every game in your library. `--launch` starts the last one.

Each game is downloaded into `<app dir>/cache/platform/` and checked against the sha256 the platform lists, then installed like a [local file](games.md#install). A good copy in the cache is reused.

| Kind | Where it goes |
| ---- | ------------- |
| Bitsy (`.bitsy`) | `bitsy-games/` on the console's drive, played by the Bitsy player. |
| Chili Beat (`.beat`) | `beat-games/` on the console's drive, played by the Chili Beat player. |

Both players come with the factory image. A game of a kind the console has no player for is skipped with a message.

## Unlink

```bash
chilichip logout
```

This forgets the token on this computer. To revoke it on the platform too, remove the device under **Settings → Devices** on the website. A revoked computer gets "Run: chilichip login" on its next request.

## Another platform

`--platform URL`, or the `CHILICHIP_PLATFORM_URL` variable, points every command here at another platform, for example a local one in development. Each address keeps its own token.

## Errors

| Message | Cause | Fix |
| ------- | ----- | --- |
| `This computer is not linked to https://platform.chilichip.eu. Run: chilichip login` | no saved token | `chilichip login` |
| `The platform no longer knows this computer: it was unlinked or revoked.` | the device was removed in Settings | `chilichip login` |
| `Linking was denied on the website.` | someone pressed **Deny** on the link page | `chilichip login` again |
| `The download of ... has the wrong checksum.` | the download was cut or changed | run the command again |
| `Cannot reach https://platform.chilichip.eu` | no network, or the platform is down | check the connection |
