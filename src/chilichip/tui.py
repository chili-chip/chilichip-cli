"""The interactive TUI: one tab per job, all calling the same functions as the commands."""
import os
import pathlib
import threading

from textual.app import App, ComposeResult
from textual.containers import Horizontal, Vertical
from textual.widgets import (Button, DataTable, Footer, Header, Input, Label,
                             Log, RadioButton, RadioSet, Select, Static,
                             TabbedContent, TabPane)
from tqdm import tqdm

from . import ChilichipError, project
from .console import Console, find_console
from .firmware import fetch_firmware, make_plan, update_console

# tqdm (the install progress bar) otherwise makes a multiprocessing lock, which starts a helper
# process that is passed stderr's fd; Textual's captured stderr has fd -1, so the install fails
tqdm.set_lock(threading.RLock())


class ChilichipApp(App):
    TITLE = 'chilichip'
    SUB_TITLE = 'ChiliChip console and game projects'
    BINDINGS = [('q', 'quit', 'Quit'), ('r', 'refresh', 'Refresh console')]
    CSS = '''
    TabbedContent { height: 1fr; }
    TabPane { padding: 1 2; height: 1fr; }
    .row { height: auto; margin-top: 1; }
    .row Button { margin-right: 1; }
    #install-path { width: 1fr; }
    #games { height: 1fr; }
    Label { margin-top: 1; color: $text-muted; }
    TabPane > Vertical { overflow-y: auto; }
    #log { height: 8; border: round $primary; }
    '''

    def __init__(self):
        super().__init__()
        self.games = []
        self.update_plan = None
        self.delete_armed = False

    def compose(self) -> ComposeResult:
        cwd = str(pathlib.Path.cwd())
        yield Header()
        with TabbedContent(initial='console'):
            with TabPane('Console', id='console'):
                yield Static('Looking for a console...', id='console-status')
                yield DataTable(id='games', cursor_type='row')
                with Horizontal(classes='row'):
                    yield Input(placeholder='Path to a .blit or .bitsy file', id='install-path')
                    yield Button('Install', id='install', variant='primary')
                with Horizontal(classes='row'):
                    yield Button('Launch', id='launch')
                    yield Button('Delete', id='delete', variant='error')
                    yield Button('Refresh', id='refresh')
            with TabPane('Update', id='update'):
                yield Static('Check for the latest loader, home screen and Bitsy player.', id='update-status')
                with Horizontal(classes='row'):
                    yield Button('Check for updates', id='check', variant='primary')
                    yield Button('Update now', id='flash', variant='warning', disabled=True)
            with TabPane('New project', id='new'):
                with Vertical():
                    yield Label('Name')
                    yield Input(placeholder='space-cat', id='new-name')
                    yield Label('Template')
                    yield Select([('Game template', 'game'), ('RPG template', 'rpg')], value='game',
                                 allow_blank=False, id='new-template')
                    yield Label('Create it in')
                    yield Input(value=cwd, id='new-folder')
                    with Horizontal(classes='row'):
                        yield Button('Create', id='create', variant='primary')
            with TabPane('Build and run', id='build'):
                with Vertical():
                    yield Label('Game folder')
                    yield Input(value=cwd, id='project-folder')
                    yield Label('Target')
                    with RadioSet(id='target'):
                        yield RadioButton('This computer', value=True, id='target-desktop')
                        yield RadioButton('Console', id='target-console')
                    with Horizontal(classes='row'):
                        yield Button('Build', id='do-build', variant='primary')
                        yield Button('Run', id='do-run')
        yield Log(id='log')
        yield Footer()

    def on_mount(self):
        os.environ.setdefault('TQDM_DISABLE', '1')  # progress bars would draw over the TUI
        self.query_one('#games', DataTable).add_columns('Title', 'Version', 'Author', 'Size')
        self.action_refresh()

    # helpers

    def write(self, line):
        """Log a line. Safe to call from worker threads."""
        try:
            self.call_from_thread(self.query_one('#log', Log).write_line, line)
        except RuntimeError:  # already on the app thread
            self.query_one('#log', Log).write_line(line)

    def background(self, job, *args):
        """Run a job in a thread; errors go to the log instead of crashing the TUI."""
        def work():
            try:
                job(*args)
            except ChilichipError as e:
                self.write(f'Error: {e.message}')
            except Exception as e:  # serial and OS errors from the device or the build
                self.write(f'Error: {e}')
        self.run_worker(work, thread=True, group='jobs')

    def set_text(self, widget_id, text):
        self.call_from_thread(self.query_one(widget_id, Static).update, text)

    def selected_game(self):
        table = self.query_one('#games', DataTable)
        if not self.games or table.cursor_row is None:
            self.write('Select a game first.')
            return None
        return self.games[table.cursor_row]

    def target(self):
        return 'console' if self.query_one('#target-console', RadioButton).value else 'desktop'

    # console tab

    def action_refresh(self):
        self.background(self.load_console)

    def load_console(self):
        try:
            port = find_console()
        except ChilichipError as e:
            self.set_text('#console-status', e.message)
            self.call_from_thread(self.show_games, [])
            return
        with Console(port) as console:
            version = console.version()
            games = console.games()
        loader = version.version if version else 'an older loader'
        self.set_text('#console-status', f'Console on {port}, running {loader}. {len(games)} installed.')
        self.call_from_thread(self.show_games, games)

    def show_games(self, games):
        self.games = games
        table = self.query_one('#games', DataTable)
        table.clear()
        for g in games:
            table.add_row(g.title or f'(block {g.block})', g.version, g.author, f'{g.size / 1024:.0f} KB')

    def with_console(self, action):
        with Console(find_console()) as console:
            action(console)
        self.load_console()

    def install(self, path):
        def action(console):
            version = console.version()
            console.install(path, loader_api=version.api if version else None)
            self.write(f'Installed {path.name}')
        self.with_console(action)

    # update tab

    def check_update(self):
        self.update_plan = None
        firmware = fetch_firmware(log=self.write)
        try:
            port = find_console()
        except ChilichipError:
            self.set_text('#update-status', 'No console found. To set up a new console, run: chilichip update --factory')
            return
        with Console(port) as console:
            plan = make_plan(firmware, console.version(), console.games())
        if not plan.lines:
            self.set_text('#update-status', f'The console is up to date ({firmware.version}).')
            return
        self.update_plan = (firmware, plan, port)
        lines = ['This update changes:', *plan.lines, 'Installed games, saves and settings are kept.']
        self.set_text('#update-status', '\n'.join(lines))
        self.call_from_thread(setattr, self.query_one('#flash', Button), 'disabled', False)

    def run_update(self):
        firmware, plan, port = self.update_plan
        self.update_plan = None
        self.call_from_thread(setattr, self.query_one('#flash', Button), 'disabled', True)
        update_console(firmware, plan, port, log=self.write)
        self.load_console()
        self.check_update()

    # new project tab

    def create(self, name, template, parent):
        folder = project.new_project(name, template, parent=parent, log=self.write)
        self.write(f'Created {folder}')
        missing = project.missing_sdks(folder.parent)
        if missing:
            self.write(f'Downloading {", ".join(missing)} next to the game...')
            project.clone_sdks(missing, folder.parent, log=self.write)
        self.call_from_thread(setattr, self.query_one('#project-folder', Input), 'value', str(folder))
        self.write('Done. Open the "Build and run" tab to try it.')

    # build tab

    def build(self, folder, target):
        game = project.build(project.find_project(folder), target, log=self.write)
        self.write(f'Built {game}')

    def run_game(self, folder, target):
        project.run_game(project.find_project(folder), target, log=self.write)
        self.write('Game started.' if target == 'console' else 'Game closed.')

    def on_button_pressed(self, event: Button.Pressed):
        button = event.button.id
        if button != 'delete':
            self.delete_armed = False

        if button == 'refresh':
            self.action_refresh()
        elif button == 'install':
            path = pathlib.Path(self.query_one('#install-path', Input).value.strip()).expanduser()
            self.background(self.install, path)
        elif button == 'launch':
            game = self.selected_game()
            if game:
                self.background(self.with_console, lambda c: c.launch_block(game.block))
        elif button == 'delete':
            game = self.selected_game()
            if game and not self.delete_armed:
                self.delete_armed = True
                self.write(f'Press Delete again to delete {game.title}. Its saves stay on the drive.')
            elif game:
                self.delete_armed = False
                self.background(self.with_console, lambda c: c.delete(game.block))
        elif button == 'check':
            self.background(self.check_update)
        elif button == 'flash' and self.update_plan:
            self.background(self.run_update)
        elif button == 'create':
            name = self.query_one('#new-name', Input).value.strip()
            template = self.query_one('#new-template', Select).value
            parent = pathlib.Path(self.query_one('#new-folder', Input).value.strip()).expanduser()
            self.background(self.create, name, template, parent)
        elif button in ('do-build', 'do-run'):
            folder = pathlib.Path(self.query_one('#project-folder', Input).value.strip()).expanduser()
            job = self.build if button == 'do-build' else self.run_game
            self.background(job, folder, self.target())
