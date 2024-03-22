from argparse import ArgumentParser

from optuna.cli import _get_parser


def _format_usage(parser: ArgumentParser) -> str:
    """Format the usage without any prefixes"""
    fmt = parser._get_formatter()
    fmt.add_usage(parser.usage, parser._actions, parser._mutually_exclusive_groups, prefix="")
    return fmt.format_help().strip()


def parse_arguments(parser, shared_actions: set | None = None):
    """Collect all optional arguments"""
    shared_actions = shared_actions or set()
    ignored_actions = {"==SUPPRESS==", "help"}

    action_groups = []
    for action_group in parser._action_groups:
        actions = {}
        for action in action_group._group_actions:
            # Skip arguments shared among all subcommands.
            if action.dest in shared_actions or action.dest in ignored_actions:
                continue
            action_data = {
                "name": action.option_strings,
                "default": f'"{action.default}"',
                "help": action.help,
                "choices": action.choices,
            }
            actions[action.dest] = action_data
        # Currently, there is no customized groups in Optuna CLI ArgumentParser and
        # action_group.title is always "action_groups". If anyone add customized groups,
        # this code should be updated.
        if actions:
            action_groups.append({"title": action_group.title, "options": actions})
    return action_groups


def parse_parser(parser: ArgumentParser, shared_actions: set[str]) -> dict:
    """Parse an ArgumentParser object into a dict."""
    data = {
        "name": "",
        "usage": _format_usage(parser),
        "prog": parser.prog,
        "action_groups": parse_arguments(parser, shared_actions=shared_actions),
    }
    return data


def parse_parsers():
    main_parser, parent_parser, command_name_to_subparser = _get_parser()
    # Collect the shared optional arguments among all subcommands.
    shared_actions_data = parse_arguments(parent_parser)
    shared_actions = shared_actions_data[0]["options"].keys()

    main_parser.prog = "optuna"
    parsed_args = parse_parser(main_parser, shared_actions)
    parsed_args["children"] = []
    for command_name, subparser in command_name_to_subparser.items():
        subparser.prog = f"optuna {command_name}"
        parsed_args["children"].append(parse_parser(subparser, shared_actions))

    parsed_args["shared_options"] = shared_actions_data[0]["options"]
    return parsed_args
