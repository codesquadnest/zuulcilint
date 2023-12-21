"""ZuuL Lint.

A linter for Zuul configuration files.
"""

import argparse
import importlib.metadata
import pathlib
import sys
from collections import defaultdict

import yaml
from jsonschema import Draft201909Validator

import zuulcilint.checker as zuul_checker
import zuulcilint.utils as zuul_utils

# Register custom yaml constructor for "encrypted/pkcs1-oaep"
yaml.SafeLoader.add_constructor(
    "!encrypted/pkcs1-oaep",
    zuul_utils.encrypted_pkcs1_oaep_constructor,
)


def lint(file_path: str, schema: dict) -> int:
    """Validate a YAML file against a JSON schema.

    Args:
    ----
        file_path: A string representing the path to the YAML file to validate.
        schema: A JSON schema to validate against.

    Returns:
    -------
        The number of validation errors encountered.
    """
    print(f"  {file_path}")
    errors = 0
    validator = Draft201909Validator(schema)

    try:
        with pathlib.Path.open(pathlib.Path(file_path), encoding="utf-8") as yaml_in:
            try:
                obj = yaml.safe_load(yaml_in)
                va_errors = validator.iter_errors(obj)
                for e in va_errors:
                    zuul_utils.print_bold("Validation error:", "error")
                    print(f"  File: {file_path}")
                    print(f"  Message: {e.message}")
                    print(f"  Path: {list(e.path)}")
                    print(f"  Schema Path: {list(e.schema_path)}\n")
                    errors += 1
            except yaml.YAMLError as e:
                print(f"YAML Parse Error: {e}")
                errors += 1
    except FileNotFoundError as e:
        print(f"{e.filename} not found!\nExiting")
        sys.exit(1)

    return errors


def lint_single_yaml_file(file_path: pathlib.Path, schema: dict) -> int:
    """Lint a single Zuul YAML file."""
    return lint(file_path, schema=schema)


def lint_all_yaml_files(file_paths: list[pathlib.Path], schema: dict) -> int:
    """Lint all Zuul YAML files."""
    return sum(lint_single_yaml_file(file_path, schema) for file_path in file_paths)


def lint_playbook_paths(zuul_yaml_files: list[pathlib.Path]) -> list[str]:
    """Lint playbook paths in all Zuul YAML files."""
    invalid_paths = []
    for file_path in zuul_yaml_files:
        jobs = zuul_utils.get_jobs_from_zuul_yaml(file_path)
        for job in jobs:
            invalid_paths.extend(
                zuul_checker.check_job_playbook_paths(job.get("job", {})),
            )
    return invalid_paths


def get_all_zuul_yaml_files(files: list[str]) -> list[pathlib.Path]:
    """Get all Zuul YAML/YML files from the specified file(s) or path(s)."""
    zuul_yaml_files = defaultdict(list)
    for file in files:
        for file_type, paths in zuul_utils.get_zuul_yaml_files(pathlib.Path(file)).items():
            zuul_yaml_files[file_type].extend(paths)

    return zuul_yaml_files


def get_all_jobs(zuul_yaml_files: list[pathlib.Path]) -> list[list[str]]:
    """Get all jobs from Zuul YAML files."""
    all_jobs = []
    for file_path in zuul_yaml_files:
        jobs = zuul_utils.get_jobs_from_zuul_yaml(file_path)
        all_jobs.append([job.get("job", {}).get("name") for job in jobs])
    return all_jobs


def print_warnings(bad_yml_files: list[str], duplicated_jobs: set[str]) -> None:
    """Print warnings."""
    nr_warnings = len(bad_yml_files) + len(duplicated_jobs)
    print(f"Total warnings: {nr_warnings}")
    if bad_yml_files:
        zuul_utils.print_bold(
            f"Found {len(bad_yml_files)} files with 'yml' extension",
            None,
        )
        for file_path in bad_yml_files:
            print(f"  {file_path}")
    if duplicated_jobs:
        zuul_utils.print_bold(f"Found {len(duplicated_jobs)} duplicate jobs", None)
        for job in duplicated_jobs:
            print(f"  {job}")


def print_results(
    errors: dict,
    invalid_playbook_paths: list[str],
) -> None:
    """Print the linting results."""
    nr_errors = errors["yaml"] + errors["playbook_paths"]
    print(f"Total errors: {nr_errors}")
    print(f"YAML errors: {errors['yaml']}")
    print(f"Playbook path errors: {errors['playbook_paths']}")
    if invalid_playbook_paths:
        print("Invalid playbook paths:")
        for path in invalid_playbook_paths:
            print(f"  {path}")
    sys.exit(1)


def main():
    """Parse command-line arguments and run the Zuul linter on the specified file(s).

    Returns
    -------
        None.
    """
    parser = argparse.ArgumentParser(prog="zuulcilint")
    parser.add_argument(
        "--version",
        action="version",
        version=importlib.metadata.version("zuulcilint"),
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
    all_zuul_yaml_files = get_all_zuul_yaml_files(args.file)
    zuul_good_yaml = all_zuul_yaml_files["good_yaml"]
    zuul_bad_yaml = all_zuul_yaml_files["bad_yaml"]
    invalid_playbook_paths = []

    # Initialize results dictionary
    results = {
        "errors": {"yaml": 0, "playbook_paths": 0},
        "warnings": {"file_extension": 0, "duplicated_jobs": 0},
    }

    # Lint all Zuul YAML files
    results["errors"]["yaml"] = lint_all_yaml_files(zuul_good_yaml, schema)
    results["warnings"]["file_extension"] = len(zuul_good_yaml)

    # Check playbook paths if specified
    if args.check_playbook_paths:
        zuul_utils.print_bold("Checking playbook paths", "info")
        invalid_playbook_paths = lint_playbook_paths(zuul_good_yaml)
        results["errors"]["playbook_paths"] = len(invalid_playbook_paths)
        for path in invalid_playbook_paths:
            print(f"  {path}")

    # Check duplicated jobs
    zuul_utils.print_bold("Checking for duplicate jobs", "info")
    duplicated_jobs = zuul_checker.check_duplicated_jobs(get_all_jobs(zuul_good_yaml))
    if duplicated_jobs:
        for job in duplicated_jobs:
            print(f"  {job}")
    else:
        print("  No duplicate jobs found")
    results["warnings"]["duplicated_jobs"] = len(duplicated_jobs)

    # Print warnings
    zuul_utils.print_bold("Warnings", "warning")
    print_warnings(zuul_bad_yaml, duplicated_jobs)

    # Print results
    if results["errors"]["yaml"] or results["errors"]["playbook_paths"]:
        zuul_utils.print_bold("Failed", "error")
        print_results(
            results["errors"],
            invalid_playbook_paths,
        )

    # Print success message
    zuul_utils.print_bold("Passed", "success")
    sys.exit(0)


if __name__ == "__main__":
    main()
