import rl.utils.click as click

from court.export.commands import export
from court.inference.commands import inference
from court.ingest.commands import ingest
from court.pipeline.commands import pipeline


@click.group()
def cli():
    pass


cli.add_command(export)
cli.add_command(inference)
cli.add_command(ingest)
cli.add_command(pipeline)


if __name__ == "__main__":
    cli()
