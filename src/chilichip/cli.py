"""The chilichip command. With no command it opens the TUI."""
import pathlib

import click

from . import __version__, platform_api, project
from .console import Console, find_console
from .firmware import (factory_install, fetch_firmware, make_plan,
                       update_console)
from .project import build, find_project, run_game

TARGET = click.option('--console', 'target', flag_value='console', help='Build for the console (.blit).')
DESKTOP = click.option('--desktop', 'target', flag_value='desktop', default=True, help='Build for this computer (default).')
PLATFORM = click.option('--platform', 'url', envvar='CHILICHIP_PLATFORM_URL', metavar='URL',
                        help=f'Chili Platform address (default {platform_api.DEFAULT_URL}, or $CHILICHIP_PLATFORM_URL).')


@click.group(invoke_without_command=True)
@click.version_option(__version__, prog_name='chilichip')
@click.pass_context
def main(ctx):
    """Update your ChiliChip console, install games, and make your own.

    Run chilichip with no command to open the interactive TUI.
    """
    if ctx.invoked_subcommand is None:
        from .tui import ChilichipApp
        ChilichipApp().run()


@main.command()
@click.option('--factory', is_flag=True, help='Set up a new or wiped console (no loader yet).')
@click.option('--force', is_flag=True, help='Flash even when the console is up to date.')
@click.option('--yes', '-y', is_flag=True, help="Don't ask before flashing.")
def update(factory, force, yes):
    """Update the console to the latest firmware: loader, home screen and Bitsy player."""
    firmware = fetch_firmware()

    if factory:
        click.echo('Factory mode writes the loader and the home screen. '
                   'Saves and other games are kept, but a game installed at 256 KB is overwritten.')
        if not yes:
            click.confirm('Continue?', abort=True)
        try:
            port = find_console()
        except click.ClickException:
            port = None  # already in BOOTSEL mode, or no loader at all
        factory_install(firmware, port)
        return

    port = find_console()
    with Console(port) as console:
        loader = console.version()
        games = console.games()

    plan = make_plan(firmware, loader, games, force)
    if not plan.lines:
        click.echo(f'The console is up to date ({firmware.version}).')
        return

    click.echo('This update changes:')
    for line in plan.lines:
        click.echo(f'  {line}')
    click.echo('Installed games, saves and settings are kept.')
    if not yes and not click.confirm('Update now?'):
        return
    update_console(firmware, plan, port)


@main.command()
@click.argument('games', nargs=-1)
@click.option('--launch', is_flag=True, help='Start the last game after installing it.')
@click.option('--from-platform', is_flag=True, help='GAMES are titles or ids from your Chili Platform library.')
@click.option('--all', 'all_games', is_flag=True, help='With --from-platform: every game in your library the console can play.')
@PLATFORM
def install(games, launch, from_platform, all_games, url):
    """Install .blit games, .bitsy and .beat files on the console.

    \b
    chilichip install space-cat.blit cat-adventure.bitsy
    chilichip install --from-platform "Cat Adventure"
    chilichip install --from-platform --all
    """
    if from_platform:
        files = platform_files(games, all_games, url)
        if not files:
            return
    else:
        if not games:
            raise click.UsageError('Name at least one .blit, .bitsy or .beat file.')
        files = []
        for name in games:
            path = pathlib.Path(name)
            if not path.is_file():
                raise click.BadParameter(f'File {name!r} does not exist.', param_hint="'GAMES...'")
            files.append((path, path.name))

    with Console(find_console()) as console:
        version = console.version()
        for i, (path, title) in enumerate(files):
            console.install(path, launch=launch and i == len(files) - 1, loader_api=version.api if version else None)
            click.echo(f'Installed {title}')


def platform_files(names, all_games, url):
    """Download the chosen library games; returns (path, title) for the ones the console can play."""
    if not names and not all_games:
        raise click.UsageError('Name a game from your library, or use --all. See: chilichip library')
    client = platform_api.Platform(url, platform_api.load_token(platform_api.platform_url(url)))
    library = client.library()
    chosen = library if all_games else platform_api.pick_games(library, names)
    files = []
    for game in chosen:
        if not platform_api.console_can_play(game):
            engine = platform_api.ENGINE_NAMES.get(game.get('engine'), game.get('engine'))
            click.echo(f'Skipped {game["title"]}: the console has no player for {engine} games.')
            continue
        click.echo(f'Downloading {game["title"]}...')
        files.append((client.download(game), game['title']))
    return files


@main.command()
@click.option('--name', help='How this computer shows in your account (default: chilichip CLI on <computer name>).')
@PLATFORM
def login(name, url):
    """Link this computer to your Chili Platform account with a code."""
    device = platform_api.login(platform_api.platform_url(url), name or platform_api.default_name())
    click.echo(f'Linked as "{device.get("name", name)}". Next: chilichip library')


@main.command()
@PLATFORM
def logout(url):
    """Forget this computer's link to Chili Platform."""
    url = platform_api.platform_url(url)
    if platform_api.forget_token(url):
        click.echo(f'Forgot the link to {url}.')
    else:
        click.echo(f'This computer was not linked to {url}.')
    click.echo(f'To revoke it for good, remove the device in Settings: {url}/settings#devices')


@main.command()
@PLATFORM
def library(url):
    """List the games in your Chili Platform library."""
    url = platform_api.platform_url(url)
    games = platform_api.Platform(url, platform_api.load_token(url)).library()
    if not games:
        click.echo('Your library is empty. Get games at ' + url)
        return
    for game in games:
        engine = platform_api.ENGINE_NAMES.get(game.get('engine'), game.get('engine'))
        note = '' if platform_api.console_can_play(game) else '  (no console player)'
        click.echo(f'{game["id"]:5d}  {game["title"]:24}  {game["author"]:16}  {engine:10}  {platform_api.size_text(game["size"])}{note}')
    click.echo('Install one with: chilichip install --from-platform "<title>"')


@main.command('list')
def list_games():
    """List the games installed on the console."""
    with Console(find_console()) as console:
        version = console.version()
        games = console.games()
    click.echo(f'Loader: {version.version if version else "unknown (older than this command)"}')
    for game in games:
        click.echo(f'{game.block:3d}  {game.title:24}  {game.version:10}  {game.author:16}  {game.size / 1024:.0f} KB')


def find_game(console, name):
    games = [g for g in console.games() if g.title.lower() == name.lower()]
    if not games:
        raise click.ClickException(f'No game called "{name}" on the console. See: chilichip list')
    return games[0]


@main.command()
@click.argument('name')
@click.option('--yes', '-y', is_flag=True, help="Don't ask first.")
def delete(name, yes):
    """Delete a game from the console. Its saves stay on the console's drive."""
    with Console(find_console()) as console:
        game = find_game(console, name)
        if yes or click.confirm(f'Delete {game.title} {game.version}?'):
            console.delete(game.block)
            click.echo(f'Deleted {game.title}')


@main.command()
@click.argument('name')
def launch(name):
    """Start an installed game by its title."""
    with Console(find_console()) as console:
        console.launch_block(find_game(console, name).block)


@main.command()
@click.argument('name')
@click.option('--template', type=click.Choice(sorted(project.TEMPLATES)), default='game', show_default=True)
@click.option('--author', help='Author for metadata.yml (default: git config user.name).')
def new(name, template, author):
    """Start a new game in a folder called NAME."""
    folder = project.new_project(name, template, author=author)
    click.echo(f'Created {folder}')

    missing = project.missing_sdks(folder.parent)
    if missing:
        click.echo(f'Missing next to your game: {", ".join(missing)}')
        if click.confirm('Download them now?', default=True):
            project.clone_sdks(missing, folder.parent)
    click.echo(f'Next: cd {name} && chilichip run')


@main.command('build')
@TARGET
@DESKTOP
def build_cmd(target):
    """Build the game in this folder."""
    game = build(find_project(), target)
    click.echo(f'Built {game}')


@main.command('run')
@TARGET
@DESKTOP
def run_cmd(target):
    """Build the game, then start it on this computer or on the console."""
    run_game(find_project(), target)


@main.command()
def doctor():
    """Check the tools, SDKs and the console."""
    checks = project.doctor()
    for check in checks:
        mark = click.style('ok ', fg='green') if check.ok else click.style('no ', fg='red')
        click.echo(f'{mark} {check.name:14} {check.detail}')
    # the console is optional: desktop builds work without it
    if not all(c.ok for c in checks if c.name != 'Console'):
        raise SystemExit(1)
