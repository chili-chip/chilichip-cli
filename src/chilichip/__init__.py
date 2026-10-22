"""chilichip: firmware updates, games and game projects for the ChiliChip console."""
import click

from ttblit import __version__  # noqa: F401  one version for both commands


class ChilichipError(click.ClickException):
    """An error with a message the user can act on. The CLI prints it without a traceback."""
