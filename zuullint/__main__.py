"""ZuuL Lint.

A linter for Zuul configuration files.
"""

import argparse
import importlib.metadata
import pathlib
import sys

import yaml
from jsonschema import Draft201909Validator

import zuullint.checker as zuul_checker
import zuullint.utils as zuul_utils

# # Register custom yaml constructor for "encrypted/pkcs1-oaep"
yaml.SafeLoader.add_constructor(
    "!encrypted/pkcs1-oaep", zuul_utils.encrypted_pkcs1_oaep_constructor,
)


def lint(f: str, schema: dict) -> int:
    """Validate a YAML file against a JSON schema.

    Args:
    ----
        f: A string representing the path to the YAML file to validate.
        schema: A JSON schema to validate against.

    Returns:
    -------
        The number of validation errors encountered.
    """
    print(f"  {f}")
    errors = 0
    validator = Draft201909Validator(schema)

    try:
        with pathlib.Path.open(pathlib.Path(f), encoding="utf-8") as yaml_in:
            try:
                obj = yaml.safe_load(yaml_in)
                va_errors = validator.iter_errors(obj)
                for e in va_errors:
                    print(e, file=sys.stderr)
                    errors += 1
            except yaml.YAMLError as e:
                print(e)
                errors += 1
    except FileNotFoundError as e:
        print(f"{e.filename} not found!\nExiting")
        sys.exit(1)
    return errors


def main():
    """Parse command-line arguments and run the Zuul linter on the specified file(s).

    Returns
    -------
        None.
    """
    parser = argparse.ArgumentParser(prog="zuullint")
    parser.add_argument(
        "--version",
        action="version",
        version=importlib.metadata.version("zuullint"),
    )
    parser.add_argument(
        "--check-playbook-paths",
        "-c",
        help="check that playbook paths are valid",
        action="store_true",
    )
    parser.add_argument("file", nargs="+", help="file(s) or paths to lint")
    parser.add_argument(
        "--schema",
        "-s",
        help="path to Zuul schema file",
        default=pathlib.Path(__file__).parent / "zuul-schema.json",
        type=pathlib.Path,
    )

    args = parser.parse_args()
    schema = zuul_utils.get_zuul_schema(schema_file=args.schema)
    zuul_yaml_files = []
    invalid_playbook_paths = []
    suspect_yml_files = []

    # Initialize a dictionary to store the number of errors encountered.
    results = {}
    results["file_extension_warnings"] = 0
    results["playbook_paths_errors"] = 0
    results["yaml_errors"] = 0

    # Get a list of Zuul YAML files from the specified path(s).
    for f in args.file:
        path = pathlib.Path(f)
        zuul_yaml_files.extend(zuul_utils.get_zuul_yaml_files(path))

    # Get warnings for files with "yml" extension.
    for f in args.file:
        path = pathlib.Path(f)
        suspect_yml_files.extend(zuul_utils.get_files_with_extension(path, "yml"))
        results["file_extension_warnings"] = len(suspect_yml_files)

    zuul_utils.print_bold(f"Linting {len(zuul_yaml_files)} files", "info")

    # Lint each Zuul YAML file.
    results["yaml_errors"] = sum(lint(f, schema=schema) for f in zuul_yaml_files)

    # Check that all playbook paths are valid.
    if args.check_playbook_paths:
        zuul_utils.print_bold("Checking playbook paths", "info")
        for f in zuul_yaml_files:
            jobs = zuul_utils.get_jobs_from_zuul_yaml(f)
            for job in jobs:
                invalid_playbook_paths.extend(
                    zuul_checker.check_job_playbook_paths(job.get("job", {})),
                )
                for path in zuul_utils.get_playbook_paths_from_job(job.get("job", {})):
                    print(f"  {path}")
        results["playbook_paths_errors"] = len(invalid_playbook_paths)

    # Print warnings.
    if results["file_extension_warnings"]:
        zuul_utils.print_bold("Warnings", "warning")
        if suspect_yml_files:
            zuul_utils.print_bold(
                f"Found {results['file_extension_warnings']} "
                "files with 'yml' extension",
                None,
            )
            for path in suspect_yml_files:
                print(f"  {path}")

    # Print results.
    if results["yaml_errors"] or results["playbook_paths_errors"]:
        nr_errors = results["yaml_errors"] + results["playbook_paths_errors"]
        zuul_utils.print_bold("Failed", "error")
        print(
            f"Total errors: {nr_errors} ",
        )
        print(f"YAML errors: {results['yaml_errors']}")
        print(f"Playbook path errors: {results['playbook_paths_errors']}")
        if invalid_playbook_paths:
            print("Invalid playbook paths:")
            for path in invalid_playbook_paths:
                print(f"  {path}")
        sys.exit(1)

    # Print success message.
    zuul_utils.print_bold("Passed", "success")
    sys.exit(0)


if __name__ == "__main__":
    main()
