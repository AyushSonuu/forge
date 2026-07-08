"""forge — client CLI. Full implementation lands in branch 11."""
from __future__ import annotations

import typer

app = typer.Typer(help="Forge client CLI.")


@app.command()
def version() -> None:
    """Print the installed Forge version."""
    from forge import __version__

    typer.echo(__version__)


if __name__ == "__main__":  # pragma: no cover
    app()
