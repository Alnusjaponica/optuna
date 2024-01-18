from argparse import _HelpAction
from argparse import _StoreConstAction
from argparse import _SubParsersAction
from argparse import ArgumentParser
from typing import Any


def _try_add_parser_attribute(data: dict, parser: ArgumentParser, attribname: str) -> None:
    """Add an attribute to the data dict if it exists on the parser."""
    attribval = getattr(parser, attribname, None)
    if not isinstance(attribval, str):
        return
    if len(attribval) > 0:
        data[attribname] = attribval


def _format_usage_without_prefix(parser: ArgumentParser) -> str:
    """Format the usage string without any prefixes."""
    fmt = parser._get_formatter()
    fmt.add_usage(parser.usage, parser._actions, parser._mutually_exclusive_groups, prefix="")
    return fmt.format_help().strip()


def parse_parser(parser: ArgumentParser, data: dict | None = None, **kwargs: Any) -> dict:
    """Parse an ArgumentParser object into a dict."""
    if data is None:
        data = {
            "name": "",
            "usage": _format_usage_without_prefix(parser),
            "prog": parser.prog,
        }

    # Add the description and epilog if they exist.
    _try_add_parser_attribute(data, parser, "description")
    _try_add_parser_attribute(data, parser, "epilog")

    for action in parser._get_positional_actions():
        # Collect the help messages for each subcommand.
        if not isinstance(action, _SubParsersAction):
            continue
        helps = {}
        for item in action._choices_actions:
            helps[item.dest] = item.help

        # Add the subcommands to the data.
        for name, subaction in action._name_parser_map.items():
            subaction.prog = f"{parser.prog} {name}"
            subdata = {
                "name": name,
                "help": helps.get(name, ""),
                "usage": _format_usage_without_prefix(subaction),
            }
            parse_parser(subaction, subdata, **kwargs)
            data.setdefault("children", []).append(subdata)

    skip_defaults = kwargs.get("skip_default_values", False)
    skip_defaults_const = kwargs.get("skip_default_const_values", False) or False

    # argparse stores the different groups as a list in parser._action_groups
    # the first element of the list holds the positional arguments, the
    # second the option arguments not in groups, and subsequent elements
    # argument groups with positional and optional parameters
    action_groups = []
    for action_group in parser._action_groups:
        options_list = []
        for action in action_group._group_actions:
            if isinstance(action, _HelpAction):
                continue

            # Quote default values for string/None types
            default = action.default
            if (
                action.default not in ["", None, True, False]
                and action.type in [None, str]
                and isinstance(action.default, str)
            ):
                default = f'"{default}"'

            # fill in any formatters, like %(default)s
            format_dict = dict(vars(action), prog=data.get("prog", ""), default=default)
            format_dict["default"] = default
            help_str = action.help or ""  # Ensure we don't print None
            try:
                help_str = help_str % format_dict
            except Exception:
                pass

            # Options have the option_strings set, positional arguments don't
            option_strings = action.option_strings
            # Skip lines for subcommands.
            if option_strings == ["==SUPPRESS=="]:
                continue
            if option_strings == []:
                options_name = [action.metavar if action.metavar else action.dest]
            else:
                options_name = option_strings

            if isinstance(action, _StoreConstAction):
                option = {
                    "name": options_name,
                    "default": default if not skip_defaults_const else "==SUPPRESS==",
                    "help": help_str,
                }
            else:
                option = {
                    "name": options_name,
                    "default": default if not skip_defaults else "==SUPPRESS==",
                    "help": help_str,
                }
            if action.choices:
                option["choices"] = action.choices
            if "==SUPPRESS==" not in option["help"]:
                options_list.append(option)

        if len(options_list) == 0:
            continue

        group = {
            "title": action_group.title,
            "description": action_group.description,
            "options": options_list,
        }

        action_groups.append(group)

    if len(action_groups) > 0:
        data["action_groups"] = action_groups

    return data
