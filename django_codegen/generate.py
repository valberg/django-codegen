from typing import List
from typing import Optional
from typing import Tuple
from typing import Union

import typer
from rich.console import Console
from rich.syntax import Syntax

from django_codegen.lib.codegen import AppDoesNotExist
from django_codegen.lib.codegen import FIELD_GENERATOR_REGISTRY
from django_codegen.lib.codegen import ModelAlreadyExists
from django_codegen.lib.codegen import ModelGenerator

app = typer.Typer()

ParsedFieldDefinitions = List[Tuple[str, str, List[str]]]


def parse_field_definitions(field_definitions: List[str]) -> ParsedFieldDefinitions:
    parsed_field_definitions: ParsedFieldDefinitions = []
    for definition in field_definitions:
        deconstructed = definition.split(":")

        if not len(deconstructed) >= 2:
            typer.secho(
                f'"{definition}" is not a valid field definition',
                fg=typer.colors.BRIGHT_RED,
                bold=True,
            )
            raise typer.Exit(code=1)

        field_name, class_name, *arguments = deconstructed

        parsed_field_definitions.append((field_name, class_name, arguments))

    return parsed_field_definitions


def print_available_field_definitions():
    for i, name in enumerate(FIELD_GENERATOR_REGISTRY.keys()):
        number = typer.style(f"{i}.", bold=True)
        typer.echo(f"  {number} {name}")


def collect_field_definitions() -> ParsedFieldDefinitions:
    definitions: ParsedFieldDefinitions = []

    while True:
        field_name: Union[str, bool] = typer.prompt(
            "Field name (Empty to continue)", default=False, show_default=False
        )

        if not field_name:
            break

        print_available_field_definitions()
        while True:
            choice = typer.prompt("Pick one", type=int)
            try:
                class_name = list(FIELD_GENERATOR_REGISTRY.keys())[choice]
                definitions.append((field_name, class_name, []))
                break
            except IndexError:
                typer.echo(f"Error: {choice} is not a valid choice.")
                continue

    return definitions


app_name_argument = typer.Argument(None)
model_name_argument = typer.Argument(None)
field_definitions_argument = typer.Argument(None)
ordering_option = typer.Option(None, "--ordering", "-o")
django_settings_option = typer.Option(None, "--django-settings", "-s")


def print_code(code):
    console = Console()
    syntax = Syntax(code, "python")
    console.print(syntax)


@app.command(help="Generate a model")
def model(
    app_name: Optional[str] = app_name_argument,
    model_name: Optional[str] = model_name_argument,
    field_definitions: Optional[List[str]] = field_definitions_argument,
    ordering: Optional[str] = ordering_option,
    django_settings: Optional[str] = django_settings_option,
):

    if not app_name:
        app_name = typer.prompt("What app does the model belong to?")

    if not model_name:
        model_name = typer.prompt("What is the name of the model?")

    if not field_definitions:
        fields = collect_field_definitions()
    else:
        fields = parse_field_definitions(field_definitions)

    generator = ModelGenerator(
        app_name=app_name,
        model_name=model_name,
        field_definitions=fields,
        ordering=ordering,
        django_settings=django_settings,
    )

    try:
        generator.check()
    except (ModelAlreadyExists, AppDoesNotExist) as exc:
        typer.echo(typer.style(str(exc), fg=typer.colors.RED, bold=True))
        raise typer.Exit(code=1)

    try:
        rendered = generator.render()
    except TypeError as exc:
        typer.echo(typer.style(str(exc), fg=typer.colors.RED, bold=True))
        raise typer.Exit(code=1)

    typer.echo(f"# App name: {app_name}")

    print_code(rendered)

    confirmation = typer.confirm("Is this what you want?", default=True)
    if confirmation:
        generator.write_model()


@app.command()
def view():
    pass


if __name__ == "__main__":
    app()
