from typing import Any

from docutils import nodes
from docutils.frontend import OptionParser
from docutils.parsers.rst import Directive
from docutils.parsers.rst import Parser
from docutils.parsers.rst.directives import unchanged
from docutils.statemachine import StringList
from docutils.utils import new_document
import sphinx

from optuna.version import __version__

from .parser import parse_parsers


def render_list(
    structured_texts: list[str | nodes.definition], settings: Any = None
) -> list[nodes.Node]:
    """
    Given a list of reStructuredText or MarkDown sections, return a docutils node list
    """
    if len(structured_texts) == 0:
        return []
    all_children = []
    for element in structured_texts:
        if isinstance(element, str):
            if settings is None:
                settings = OptionParser(components=(Parser,)).get_default_values()
            document = new_document(None, settings)
            Parser().parse(element + "\n", document)
            all_children += document.children
        elif isinstance(element, nodes.definition):
            all_children += element

    return all_children


def print_action_groups(data: dict[str, Any], settings: Any = None) -> list[nodes.section]:
    """
    Process all 'action groups', which are also include 'Options' and 'Required
    arguments'.

    Return:
        A list of nodes.section.
    """
    nodes_list = []
    for action_group in data["action_groups"]:
        # Every action group is comprised of a section, holding a title, the description, and the option group (members)
        section = nodes.section(ids=[action_group["title"].replace(" ", "-").lower()])
        section += nodes.title(action_group["title"], action_group["title"])

        items = []
        # Iterate over action group members
        for subcommand, entry in action_group["options"].items():
            arg = []
            if "choices" in entry:
                arg.append(
                    f"Possible choices: {', '.join(str(c) for c in entry['choices'])}\n"
                )
            if "help" in entry:
                arg.append(entry["help"])

            default = entry.get("default")
            if default is not None and default not in [
                '"==SUPPRESS=="',
                "==SUPPRESS==",
            ]:
                if default == "":
                    arg.append('Default: ""')
                else:
                    arg.append(f"Default: {default}")

            term = ", ".join(entry["name"])
            items.append(
                nodes.option_list_item(
                    "",
                    nodes.option_group("", nodes.option_string(text=term)),
                    nodes.description("", *render_list(arg, settings)),
                )
            )

        section += nodes.option_list("", *items)
        nodes_list.append(section)
    return nodes_list


def create_section(child: dict[str, Any], name: str | None = None, settings: Any = None):
    # Create a new section for each subcommand.
    name = child["name"]
    sec = nodes.section(ids=name)
    sec += nodes.title(name, name)

    sec += nodes.literal_block(text=child["usage"])
    for x in print_action_groups(child, settings=settings):
        sec += x

    return sec


class ArgParseDirective(Directive):
    has_content = True
    option_spec = dict(
        deprecated=unchanged,
    )

    def _nested_parse_paragraph(self, text: str) -> nodes.paragraph:
        content = nodes.paragraph()
        self.state.nested_parse(StringList(text.split("\n")), 0, content)
        return content

    def run(self) -> list[nodes.Node]:
        # Set deprecated subcommand if specified.
        self.deprecated_subcommand = self.options.get("deprecated_subcommand")

        parsed_args = parse_parsers()

        # Add common contents to the document.
        items = []
        items.extend(
            create_section(
                parsed_args,
                settings=self.state.document.settings,
            )
        )
        items.extend(
            create_section(
                parsed_args["shared_options"],
                name="Shared Options",
                settings=self.state.document.settings,
            )
        )
        for child in parsed_args["children"]:
            if child["name"] in self.deprecated_subcommand:
                continue
            items.extend(
                create_section(
                    child,
                    settings=self.state.document.settings,
                )
            )
        return items


def setup(app: sphinx.application.Sphinx) -> dict[str, bool | str]:
    app.add_directive("argparse", ArgParseDirective)
    return {"parallel_read_safe": True, "version": __version__}
