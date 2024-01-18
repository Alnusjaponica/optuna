import importlib
import sys
from typing import Any

import sphinx
from docutils import nodes
from docutils.frontend import OptionParser
from docutils.parsers.rst import Directive, Parser
from docutils.parsers.rst.directives import flag, unchanged
from docutils.statemachine import StringList
from docutils.utils import new_document

from sphinxarg.parser import parse_parser

from . import __version__


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
    if "action_groups" in data:
        for action_group in data["action_groups"]:
            # Every action group is comprised of a section, holding a title, the description, and the option group (members)
            section = nodes.section(ids=[action_group["title"].replace(" ", "-").lower()])
            section += nodes.title(action_group["title"], action_group["title"])

            desc = []
            if action_group["description"]:
                desc.append(action_group["description"])

            # Render appropriately
            for element in render_list(desc):
                section += element

            items = []
            # Iterate over action group members
            for entry in action_group["options"]:
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


def print_subcommands(
    data: dict[str, Any], settings: Any = None, deprecated_subcommand: list[str] | None = None
) -> list[nodes.section]:  # noqa: N803
    """
    Each subcommand is a dictionary with the following keys:

    ['action_groups', 'usage', 'name', 'help']

    In essence, this is all tossed in a new section with the title 'name'.
    Apparently there can also be a 'description' entry.
    """
    deprecated_subcommand = deprecated_subcommand or []

    # If there are no subcommands, then return an empty list.
    if "children" not in data:
        return []

    # Otherwise, create a new section for each subcommand.
    # Add subcommands heading.
    subcommands = nodes.section(ids=["Sub-commands"])
    subcommands += nodes.title("Sub-commands", "Sub-commands")

    items = []
    for child in data["children"]:
        # Skip deprecated subcommands.
        if child["name"] in deprecated_subcommand:
            continue

        # Create a new section for each subcommand.
        sec = nodes.section(ids=[child["name"]])
        sec += nodes.title(child["name"], child["name"])

        # Add the description if it exists.
        desc = [child.get("description") or child.get("help") or "Undocumented"]

        for element in render_list(desc):
            sec += element
        sec += nodes.literal_block(text=child["usage"])
        for x in print_action_groups(child, settings=settings):
            sec += x

        for x in print_subcommands(child, settings=settings):
            sec += x

        if "epilog" in child and child["epilog"]:
            for element in render_list([child["epilog"]]):
                sec += element

        subcommands += sec
    items.append(subcommands)

    return items


def ensure_unique_ids(items: list[nodes.Node]) -> None:
    """
    If action groups are repeated, then links in the table of contents will
    just go to the first of the repeats. This may not be desirable, particularly
    in the case of subcommands where the option groups have different members.
    This function updates the title IDs by adding _repeatX, where X is a number
    so that the links are then unique.
    """
    s = set()
    for item in items:
        for n in item.traverse(descend=True, siblings=True, ascend=False):
            if isinstance(n, nodes.section):
                ids = n["ids"]
                for idx, id in enumerate(ids):
                    if id not in s:
                        s.add(id)
                    else:
                        i = 1
                        while f"{id}_repeat{i}" in s:
                            i += 1
                        ids[idx] = f"{id}_repeat{i}"
                        s.add(ids[idx])
                n["ids"] = ids


class ArgParseDirective(Directive):
    has_content = True
    option_spec = dict(
        module=unchanged,
        func=unchanged,
        prog=unchanged,
        deprecated_subcommand=unchanged,
        # Options to skip parts of the parser.
        nodefault=flag,
        nodefaultconst=flag,
        nosubcommands=unchanged,
        noepilog=unchanged,
        nodescription=unchanged,
    )

    def _nested_parse_paragraph(self, text: str) -> nodes.paragraph:
        content = nodes.paragraph()
        self.state.nested_parse(StringList(text.split("\n")), 0, content)
        return content

    def run(self) -> list[nodes.Node]:
        # Import the function to create a parser to be documented.
        if "module" in self.options and "func" in self.options:
            module_name = self.options["module"]
            parser_generator = self.options["func"]
        else:
            raise self.error("No :module: or :func: specified.")
        try:
            mod = importlib.import_module(module_name)
        except ImportError:
            raise self.error(
                'Failed to import "{}" from "{}".\n{}'.format(
                    parser_generator, module_name, sys.exc_info()[1]
                )
            )

        # Generate the parser.
        main_parser_generator = getattr(mod, parser_generator)
        main_parser, _ = main_parser_generator()
        # Set prog if specified.
        main_parser.prog = self.options.get("prog") or main_parser.prog
        # Set deprecated subcommand if specified.
        self.deprecated_subcommand = self.options.get("deprecated_subcommand")

        # Parse the parser.
        result = parse_parser(
            main_parser,
            skip_default_values="nodefault" in self.options,
            skip_default_const_values="nodefaultconst" in self.options,
        )

        # Add common contents to the document.
        items = []
        if "description" in result and "nodescription" not in self.options:
            items.append(self._nested_parse_paragraph(result["description"]))
        items.append(nodes.literal_block(text=result["usage"]))
        items.extend(
            print_action_groups(
                result,
                settings=self.state.document.settings,
            )
        )
        if "nosubcommands" not in self.options:
            items.extend(
                print_subcommands(
                    result,
                    settings=self.state.document.settings,
                    deprecated_subcommand=self.deprecated_subcommand,
                )
            )
        if "epilog" in result and "noepilog" not in self.options:
            items.append(self._nested_parse_paragraph(result["epilog"]))

        # Traverse the returned nodes, modifying the title IDs as necessary to avoid repeats
        ensure_unique_ids(items)

        return items


def setup(app: sphinx.application.Sphinx) -> dict[str, bool | str]:
    app.add_directive("argparse", ArgParseDirective)
    return {"parallel_read_safe": True, "version": __version__}
