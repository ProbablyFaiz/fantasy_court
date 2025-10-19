import rl.utils.click as click

from court.inference.commands import inference
from court.ingest.commands import ingest


@click.group()
def cli():
    pass


cli.add_command(inference)
cli.add_command(ingest)


if __name__ == "__main__":
    cli()
