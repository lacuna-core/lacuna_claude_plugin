import typer
from rich.console import Console

app = typer.Typer(help="lacuna CLI")
console = Console()


@app.command()
def version() -> None:
    """Print the current version."""
    from lacuna import __version__

    console.print(__version__)
