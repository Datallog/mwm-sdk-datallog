import argparse


from logger import Logger
from errors import DatallogError

logger = Logger(__name__)

parser = argparse.ArgumentParser(
    prog="datallog",
    description="Datallog is a tool for managing deployments.",
    usage="""datallog [-v | --version] [-h | --help] [-C <path>] <command> [<args>]""",
)
version = "1.0.0"

parser.add_argument(
    "-v", "--version", action="version", version=f"Datallog CLI {version}"
)


# Subparsers for git commands
subparsers = parser.add_subparsers(
    dest="command",
    title="Datallog Commands",
    description="Available commands for managing deployments",
    help='Use "datallog <command> --help" for more information on a command',
)
subparsers.required = True  # Make selecting a command mandatory


# --- 'create-project' command ---
parser_project = subparsers.add_parser(
    "create-project",
    help="Create a new deployment",
    usage="""datallog create-project [options]""",
    formatter_class=argparse.RawTextHelpFormatter,
)

parser_project.add_argument(
    "name",
    metavar="<name>",
    type=str,
    nargs="?",
    default="",
    help="Name of the deployment",
)

# --- 'create-app' command ---
parser_create_app = subparsers.add_parser(
    "create-app",
    help="Create a new application in the current deployment",
    usage="""datallog create-app [options] <app_name>""",
    formatter_class=argparse.RawTextHelpFormatter,
)
parser_create_app.add_argument(
    "app_name",
    metavar="<app_name>",
    type=str,
    help="Name of the application to create",
)


# --- 'install' command ---
parser_install = subparsers.add_parser(
    "install",
    help="Install a package into the current deployment",
    usage="""datallog install [options] <package> ...""",
    formatter_class=argparse.RawTextHelpFormatter,
)
package_group = parser_install.add_mutually_exclusive_group(required=True)
package_group.add_argument(
    "-r",
    "--requirements",
    metavar="<file>",
    default=None,
    help="Install packages from a requirements file",
)
package_group.add_argument(
    "packages",
    metavar="package",
    nargs="*",
    default=[],
    help="Install one or more packages directly",
)

# --- 'uninstall' command ---
parser_uninstall = subparsers.add_parser(
    "uninstall",
    help="Uninstall a package of the current deployment",
    usage="""datallog uninstall [options] <package> ...""",
    formatter_class=argparse.RawTextHelpFormatter,
)
uninstall_package_group = parser_uninstall.add_mutually_exclusive_group(required=True)

uninstall_package_group.add_argument(
    "-r",
    "--requirements",
    metavar="<file>",
    default=None,
    help="Uninstall all packages from a requirements file",
)
uninstall_package_group.add_argument(
    "packages",
    metavar="package",
    nargs="*",
    default=[],
    help="Uninstall one or more packages directly",
)

# --- 'run' command ---
parser_run = subparsers.add_parser(
    "run",
    help="Run a script in the current deployment",
    usage="""datallog run [options] <app_name> [--seed <seed>] [--seed-file <seed_file>] [--parallelism <n>] [--log-to-dir <dir>]""",
    formatter_class=argparse.RawTextHelpFormatter,
)

parser_run.add_argument(
    "app_name",
    metavar="<app_name>",
    help="The name of the application to run",
)
seed_group = parser_run.add_mutually_exclusive_group()
seed_group.add_argument(
    "-s",
    "--seed",
    metavar="<seed>",
    default=None,
    help="Optional seed value for the application",
)
seed_group.add_argument(
    "-f",
    "--seed-file",
    metavar="<seed_file>",
    default=None,
    help="Optional file containing seed data for the application",
)


parser_run.add_argument(
    "-p",
    "--parallelism",
    metavar="<n>",
    type=int,
    default=1,
    help="Number of parallel workers to use (default: 1)",
)


parser_run.add_argument(
    "-l",
    "--log-to-dir",
    metavar="<log_to_dir>",
    type=str,
    default=None,
    help="Directory to log the output of the application",
)

# --- 'push' command ---
parser_push = subparsers.add_parser(
    "push",
    help="Push the current deployment to the Datallog service",
    usage="""datallog push [options]""",
    formatter_class=argparse.RawTextHelpFormatter,
)

# --- 'login' command ---
parser_login = subparsers.add_parser(
    "login",
    help="Log in to the Datallog service",
    usage="""datallog login [options]""",
    formatter_class=argparse.RawTextHelpFormatter,
)

# --- 'logout' command ---
parser_logout = subparsers.add_parser(
    "logout",
    help="Log out of the Datallog service",
    usage="""datallog logout [options]""",
    formatter_class=argparse.RawTextHelpFormatter,
)

# --- 'sdk-update' command ---
parser_sdk_update = subparsers.add_parser(
    "sdk-update",
    help="Update the Datallog SDK to the latest version",
    usage="""datallog sdk-update [options]""",
    formatter_class=argparse.RawTextHelpFormatter,
)

# --- 'purge' command ---
parser_purge = subparsers.add_parser(
    "purge",
    help="Purge the local cache and logs for the current deployment",
    usage="""datallog purge""",
    formatter_class=argparse.RawTextHelpFormatter,
)

# --- Example of how to parse arguments ---
if __name__ == "__main__":
    try:
        logger.info("Datallog CLI")
        args = parser.parse_args()
        if args.command == "run":
            from subcommands.run import run
            run(args)

        elif args.command == "push":
            from subcommands.push import push
            push(args)

        elif args.command == "login":
            from subcommands.login import login
            login(args)

        elif args.command == "logout":
            from subcommands.logout import logout
            logout(args)

        elif args.command == "create-project":
            from subcommands.create_project import create_project
            create_project(args)

        elif args.command == "install":
            from subcommands.install import install
            install(args)
        elif args.command == "uninstall":
            from subcommands.uninstall import uninstall
            uninstall(args)
        elif args.command == "create-app":
            from subcommands.create_app import create_app
            create_app(args)
        elif args.command == "purge":
            from subcommands.purge import purge
            purge(args)
        else:
            parser.print_help()
    except DatallogError as e:
        logger.error(e.message)
        print(f"\033[91m{e.message}\033[0m")
