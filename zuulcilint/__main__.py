"""ZuuL Lint.

A linter for Zuul configuration files.
"""

from __future__ import annotations

import argparse
import importlib.metadata
import pathlib
import sys
from collections import defaultdict

import yaml
from jsonschema import Draft201909Validator

import zuulcilint.checker as zuul_checker
import zuulcilint.utils as zuul_utils
from zuulcilint.utils import MsgSeverity, ZuulObject

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
    print(f"{file_path}")
    errors = 0
    validator = Draft201909Validator(schema)

    try:
        with pathlib.Path.open(pathlib.Path(file_path), encoding="utf-8") as yaml_in:
            try:
                obj = yaml.safe_load(yaml_in)
                va_errors = validator.iter_errors(obj)
                for e in va_errors:
                    zuul_utils.print_bold("Validation error:", MsgSeverity.ERROR)
                    print(f"File: {file_path}")
                    print(f"Message: {e.message}")
                    print(f"Path: {list(e.path)}")
                    print(f"Schema Path: {list(e.schema_path)}\n")
                    errors += 1
            except yaml.YAMLError as e:
                print(f"YAML Parse Error: {e}")
                errors += 1
    except FileNotFoundError as e:
        print(f"{e.filename} not found!\nExiting")
        sys.exit(1)

    return errors


def lint_single_yaml_file(file_path: pathlib.Path, schema: dict) -> int:
    """Lint a single Zuul YAML file.

    Args:
    ----
        file_path: A string representing the path to the YAML file to validate.
        schema: A JSON schema to validate against.

    Returns:
    -------
        The number of validation errors encountered.
    """
    return lint(file_path, schema=schema)


def lint_all_yaml_files(file_paths: list[pathlib.Path], schema: dict) -> int:
    """Lint all Zuul YAML files.

    Args:
    ----
        file_paths: A list of strings representing the paths to the YAML files to validate.
        schema: A JSON schema to validate against.

    Returns:
    -------
        The number of validation errors encountered.
    """
    return sum(lint_single_yaml_file(file_path, schema) for file_path in file_paths)


def lint_playbook_paths(zuul_yaml_files: list[pathlib.Path]) -> list[str]:
    """Lint playbook paths in all Zuul YAML files.

    Args:
    ----
        zuul_yaml_files: A list of Zuul YAML files.

    Returns:
    -------
        A list of invalid playbook paths.
    """
    invalid_paths = []
    for file_path in zuul_yaml_files:
        jobs = zuul_utils.get_zuul_object_from_yaml(ZuulObject.JOB, file_path)
        for job in jobs:
            invalid_paths.extend(
                zuul_checker.check_job_playbook_paths(job.get(ZuulObject.JOB.value, {})),
            )
    return invalid_paths


def get_all_zuul_yaml_files(files: list[str]) -> list[pathlib.Path]:
    """Get all Zuul YAML/YML files from the specified file(s) or path(s).

    Args:
    ----
        files: A list of strings representing the file(s) or path(s) to lint.

    Returns:
    -------
        A list of Zuul YAML/YML files.
    """
    zuul_yaml_files = defaultdict(list)
    for file in files:
        for file_type, paths in zuul_utils.get_zuul_yaml_files(pathlib.Path(file)).items():
            zuul_yaml_files[file_type].extend(paths)

    return zuul_yaml_files


def get_all_zuul_objects_by_type(
    zuul_yaml_files: list[pathlib.Path],
    zuul_obj: ZuulObject,
) -> list[dict]:
    """Get all Zuul objects from provided Zuul YAML files.

    Args:
    ----
        zuul_yaml_files: A list of Zuul YAML files.
        zuul_obj: A ZuulObject enum.

    Returns:
    -------
        A list of Zuul objects.
    """
    all_zuul_objects = []
    for file_path in zuul_yaml_files:
        zuul_objects = zuul_utils.get_zuul_object_from_yaml(zuul_obj, file_path)
        all_zuul_objects.extend(zuul_objects)
    return all_zuul_objects


def print_warnings(
    warnings: dict,
    severity: MsgSeverity = MsgSeverity.WARNING,
) -> None:
    """Print warnings.

    Args:
    ----
        warnings: A dictionary containing warnings.
        severity: A MsgSeverity enum.

    Returns:
    -------
        None.
    """
    n_bad_yaml = len(warnings["warnings"]["bad_yaml_files"])
    n_duplicate_jobs = len(warnings["warnings"]["duplicated_jobs"])
    n_nodeset = len(warnings["warnings"]["inexistent_nodesets"])

    if n_bad_yaml == 0 and n_duplicate_jobs == 0 and n_nodeset == 0:
        return

    if severity == MsgSeverity.WARNING:
        zuul_utils.print_bold("Warnings", MsgSeverity.WARNING)
        print(f"Total {severity.value}s: {n_duplicate_jobs + n_nodeset}")

    if n_bad_yaml:
        zuul_utils.print_bold(f"File extension {severity.value}s:", severity)
        zuul_utils.print_bold(
            f"Found {n_bad_yaml} files with 'yml' extension",
            None,
        )
        for file_path in warnings["warnings"]["bad_yaml_files"]:
            print(f"{file_path}")

    if n_duplicate_jobs:
        zuul_utils.print_bold(f"Duplicate job {severity.value}s:", severity)
        zuul_utils.print_bold(f"Found {n_duplicate_jobs} duplicate jobs", None)
        for job in warnings["warnings"]["duplicated_jobs"]:
            print(f"{job}")

    if n_nodeset:
        zuul_utils.print_bold(f"Inexistent nodeset {severity.value}s:", severity)
        zuul_utils.print_bold(f"Found {n_nodeset} inexistent nodesets", None)
        for nodeset in warnings["warnings"]["inexistent_nodesets"]:
            print(f"{nodeset}")


def print_results(
    results: dict,
    warnings_as_errors,
    ignore_warnings,
) -> None:
    """Print the linting results.

    Args:
    ----
        results: A dictionary containing linting results.
        warnings_as_errors: A boolean indicating whether to handle warnings as errors.
        ignore_warnings: A boolean indicating whether to ignore warnings.

    Returns:
    -------
        None.
    """
    duplicated_jobs = results["warnings"]["duplicated_jobs"]
    inexistent_nodesets = results["warnings"]["inexistent_nodesets"]
    bad_yaml_files = results["warnings"]["bad_yaml_files"]
    total_semaphore_errors = results["errors"]["duplicated_semaphores"]
    total_yaml_errors = results["errors"]["yaml"]
    total_playbook_path_errors = results["errors"]["playbook_paths"]
    total_warnings = len(bad_yaml_files) + len(duplicated_jobs) + len(inexistent_nodesets)
    total_errs = total_yaml_errors + total_playbook_path_errors + total_semaphore_errors
    extra_msg = ""

    # --warnings-as-errors flag has higher precedence than --ignore-warnings
    if warnings_as_errors:
        total_errs += total_warnings
        if bad_yaml_files:
            extra_msg += f"\nFile extension errors: {len(bad_yaml_files)}"
        if duplicated_jobs:
            extra_msg += f"\nDuplicated jobs errors: {len(duplicated_jobs)}"
        if inexistent_nodesets:
            extra_msg += f"\nInexistent nodesets errors: {len(inexistent_nodesets)}"
        print_warnings(warnings=results, severity=MsgSeverity.ERROR)
    elif not ignore_warnings:
        print_warnings(warnings=results)

    if total_errs == 0:
        zuul_utils.print_bold("Passed", MsgSeverity.SUCCESS)
        sys.exit(0)

    zuul_utils.print_bold("Failed", MsgSeverity.ERROR)
    err_msg = f"Total errors: {total_errs}\n"

    if total_semaphore_errors:
        err_msg += f"Duplicated semaphores: {total_semaphore_errors}"
    if total_playbook_path_errors:
        err_msg += f"\nPlaybook path errors: {total_playbook_path_errors}"
    if total_yaml_errors:
        err_msg += f"\nYAML validation errors: {total_yaml_errors}"

    zuul_utils.print_bold(f"{err_msg + extra_msg}", MsgSeverity.ERROR)
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
    parser.add_argument(
        "--ignore-warnings",
        "-i",
        help="ignore warnings",
        action="store_true",
    )
    parser.add_argument(
        "--warnings-as-errors",
        help="handle warnings as errors",
        action="store_true",
    )

    args = parser.parse_args()
    schema = zuul_utils.get_zuul_schema(schema_file=args.schema)
    all_zuul_yaml_files = get_all_zuul_yaml_files(args.file)
    zuul_good_yaml = all_zuul_yaml_files["good_yaml"]
    zuul_bad_yaml = all_zuul_yaml_files["bad_yaml"]

    # Initialize results dictionary
    results = {
        "errors": {"duplicated_semaphores": 0, "playbook_paths": 0, "yaml": 0 },
        "warnings": {
            "duplicated_jobs": [],
            "inexistent_nodesets": [],
            "bad_yaml_files": zuul_bad_yaml,
        },
    }

    # Lint all Zuul YAML files
    results["errors"]["yaml"] = lint_all_yaml_files(zuul_good_yaml, schema)

    # Check playbook paths if specified
    if args.check_playbook_paths:
        zuul_utils.print_bold("Checking playbook paths", MsgSeverity.INFO)
        invalid_playbook_paths = lint_playbook_paths(zuul_good_yaml)
        if invalid_playbook_paths:
            results["errors"]["playbook_paths"] = len(invalid_playbook_paths)
            zuul_utils.print_bold("Invalid playbook paths:", MsgSeverity.ERROR)
            for path in invalid_playbook_paths:
                print(f"{path}")
        else:
            print("No invalid playbook paths")

    # Check duplicated jobs
    zuul_utils.print_bold("Checking for duplicate jobs", MsgSeverity.INFO)
    jobs_dict = {}
    for yaml_file in zuul_good_yaml:
        jobs_dict[yaml_file] = get_all_zuul_objects_by_type([yaml_file], ZuulObject.JOB)

    duplicated_jobs = zuul_checker.check_duplicated_jobs(jobs_dict)

    if duplicated_jobs:
        for job in duplicated_jobs:
            print(f"{job}")
    else:
        print("No duplicate jobs found")
    results["warnings"]["duplicated_jobs"] = duplicated_jobs

    # Check for inexistent nodesets
    zuul_utils.print_bold("Checking for inexistent nodesets", MsgSeverity.INFO)
    inexistent_nodesets = zuul_checker.check_inexistent_nodesets(
        get_all_zuul_objects_by_type(zuul_good_yaml, ZuulObject.NODESET),
        get_all_zuul_objects_by_type(zuul_good_yaml, ZuulObject.JOB),
    )
    if inexistent_nodesets:
        for nodeset in inexistent_nodesets:
            print(f"{nodeset}")
    else:
        print("No inexistent nodesets found")
    results["warnings"]["inexistent_nodesets"] = inexistent_nodesets

    # Check for duplicate semaphore in job and job.run
    zuul_utils.print_bold("Checking for duplicate semaphore", MsgSeverity.INFO)
    duplicate_semaphore = zuul_checker.check_duplicate_semaphore(
        get_all_zuul_objects_by_type(zuul_good_yaml, ZuulObject.JOB),
    )
    if duplicate_semaphore:
        for semaphore in duplicate_semaphore:
            print(f"{semaphore}")
    else:
        print("No duplicate semaphore found")
    results["errors"]["duplicated_semaphores"] = len(duplicate_semaphore)

    # Print results
    print_results(
        results,
        args.warnings_as_errors,
        args.ignore_warnings,
    )


if __name__ == "__main__":
    main()
