import os
from abc import ABC
from abc import abstractmethod
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from typing import Dict
from typing import List
from typing import Optional
from typing import Tuple
from typing import Union

import django
from black import FileMode
from black import format_file_in_place
from black import WriteBack
from django.apps import apps
from jinja2 import Template


class ModelAlreadyExists(Exception):
    def __init__(self, app_name, model_name):
        self.app_name = app_name
        self.model_name = model_name

    def __str__(self):
        return (
            f"The app '{self.app_name}' "
            f"already has a model called {self.model_name}."
        )


class AppDoesNotExist(Exception):
    def __init__(self, app_name):
        self.app_name = app_name

    def __str__(self):
        return f"There is no app named {self.app_name}."


class BaseGenerator(ABC):

    template: str

    @abstractmethod
    def get_context(self):
        pass

    def render(self):
        template = Template(self.template)
        return template.render(self.get_context())


FIELD_GENERATOR_REGISTRY = dict()


@dataclass
class FieldGenerator:
    name: str

    required_arguments: Optional[List[Union[str, Tuple[str, type, Any]]]] = None

    template: str = (
        "{{ field_name }} = models.{{ class_name }}"
        "({% for argument in arguments %}"
        "{{ argument }}{% if not loop.last %}, {% endif %}"
        "{% endfor %})"
    )

    argument_map = dict(
        null="null=True",
        blank="blank=True",
        max_length="max_length={value}",
        default="default={value}",
        to="to='{value}'",
    )

    def __post_init__(self):
        FIELD_GENERATOR_REGISTRY[self.name] = self

    def _parse_arguments(self, arguments: List[str]):
        all_arguments: Dict[str, str] = {}

        for argument in arguments:
            argument_split = argument.split("=")
            if len(argument_split) == 1:
                all_arguments[argument_split[0]] = self.argument_map[argument]
            elif len(argument_split) > 1:
                all_arguments[argument_split[0]] = argument_split[1]

        if self.required_arguments:
            for argument in self.required_arguments:
                if isinstance(argument, str) and argument not in all_arguments:
                    raise Exception(f"{argument} is required")

                if isinstance(argument, tuple):
                    argument_name, typ, default = argument
                    if argument_name not in all_arguments:
                        all_arguments[argument_name] = default

                    try:
                        typ(all_arguments[argument_name])
                    except ValueError:
                        raise TypeError(
                            f'"{argument}" should be of type "{typ.__name__}"'
                        )

        return [
            self.argument_map.get(key).format(value=value)
            for key, value in all_arguments.items()
        ]

    def render(self, field_name: str, arguments: List[str]):
        template = Template(self.template)
        parsed_arguments = self._parse_arguments(arguments)
        return template.render(
            dict(
                field_name=field_name, class_name=self.name, arguments=parsed_arguments
            )
        )

    def get_context(self):
        return dict(class_name=self.name)


BigIntegerFieldGenerator = FieldGenerator("BigIntegerField")
BinaryFieldGenerator = FieldGenerator("BinaryField")
BooleanFieldGenerator = FieldGenerator("BooleanField")
CharFieldGenerator = FieldGenerator(
    "CharField", required_arguments=[("max_length", int, 250)]
)
DateFieldGenerator = FieldGenerator("DateField")
DateTimeFieldGenerator = FieldGenerator("DateTimeField")
DecimalFieldGenerator = FieldGenerator("DecimalField")
DurationFieldGenerator = FieldGenerator("DurationField")
EmailFieldGenerator = FieldGenerator("EmailField")
FileFieldGenerator = FieldGenerator("FileField")
FilePathFieldGenerator = FieldGenerator("FilePathField")
FloatFieldGenerator = FieldGenerator("FloatField")
ImageFieldGenerator = FieldGenerator("ImageField")
IntegerFieldGenerator = FieldGenerator("IntegerField")
GenericIPAddressFieldGenerator = FieldGenerator("GenericIPAddressField")
NullBooleanFieldGenerator = FieldGenerator("NullBooleanField")
PositiveIntegerFieldGenerator = FieldGenerator("PositiveIntegerField")
PositiveSmallIntegerFieldGenerator = FieldGenerator("PositiveSmallIntegerField")
SlugFieldGenerator = FieldGenerator("SlugField")
SmallAutoFieldGenerator = FieldGenerator("SmallAutoField")
SmallIntegerFieldGenerator = FieldGenerator("SmallIntegerField")
TextFieldGenerator = FieldGenerator("TextField")
TimeFieldGenerator = FieldGenerator("TimeField")
URLFieldGenerator = FieldGenerator("URLField")
UUIDFieldGenerator = FieldGenerator("UUIDField")

ForeignKeyGenerator = FieldGenerator("ForeignKey", required_arguments=["to"])
OneToOneFieldGenerator = FieldGenerator("OneToOneField", required_arguments=["to"])
ManyToManyFieldGenerator = FieldGenerator("ManyToManyField", required_arguments=["to"])


@dataclass
class ModelGenerator(BaseGenerator):

    app_name: str
    model_name: str
    field_definitions: List[Tuple[str, str, List[str]]]

    ordering: str
    django_settings: str

    template: str = """class {{ model_name }}(models.Model):
    class Meta:
        verbose_name = "{{ model_name }}"
        verbose_name_plural = "{{ model_name }}s"
        {%- if ordering %}
        ordering = "{{ ordering }}"
        {%- endif %}
    {% for field in fields %}
    {{ field }}
    {% endfor %}
    """

    def get_context(self):
        return dict(
            model_name=self.model_name, fields=self.get_fields(), ordering=self.ordering
        )

    def get_fields(self) -> List[FieldGenerator]:
        fields = []
        for field_name, class_name, arguments in self.field_definitions:
            field_generator_class = FIELD_GENERATOR_REGISTRY[class_name]
            fields.append(
                field_generator_class.render(field_name=field_name, arguments=arguments)
            )
        return fields

    def check(self):
        if not os.getenv("DJANGO_SETTINGS_MODULE"):
            os.environ["DJANGO_SETTINGS_MODULE"] = self.django_settings

        django.setup()

        if self.app_name not in apps.app_configs:
            raise AppDoesNotExist(app_name=self.app_name)

        app = apps.get_app_config(self.app_name)
        if self.model_name.lower() in app.models:
            raise ModelAlreadyExists(app_name=self.app_name, model_name=self.model_name)

    def write_model(self):
        app = apps.get_app_config(self.app_name)
        file_path = Path(app.models_module.__file__)
        with file_path.open("a") as model_file:
            model_file.write(f"\n\n{self.render()}")

        # Format file with black to make stuff nicer (a.k.a. I'm lazy)
        format_file_in_place(
            file_path, fast=False, mode=FileMode(), write_back=WriteBack.YES
        )
