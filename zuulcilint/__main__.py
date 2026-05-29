"""ZuuL Lint.

A linter for Zuul configuration files.
"""

from __future__ import annotations

import argparse
import fnmatch
import importlib.metadata
import pathlib
import sys
from collections import defaultdict

import yaml
from jsonschema import Draft201909Validator

import zuulcilint.checker as zuul_checker
import zuulcilint.utils as zuul_utils
from zuulcilint.config import load_config
from zuulcilint.utils import MsgSeverity, ZuulObject

# Register constructors for custom YAML tags
yaml.SafeLoader.add_constructor(
    "!encrypted/pkcs1-oaep",
    zuul_utils.encrypted_pkcs1_oaep_constructor,
)
yaml.SafeLoader.add_constructor(
    "!inherit",
    zuul_utils.override_control_tags_constructor,
)
yaml.SafeLoader.add_constructor(
    "!override",
    zuul_utils.override_control_tags_constructor,
)

# Rules whose default severity is "warning" and which can be promoted to "error"
# via config. Each tuple is (rule_name, warning_bucket_key).
_RULE_WARNING_BUCKETS: tuple[tuple[str, str], ...] = (
    ("check-duplicated-jobs", "duplicated_jobs"),
    ("check-inexistent-nodesets", "inexistent_nodesets"),
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


def _apply_file_filters(
    yaml_files_dict: dict,
    include_patterns: list[str],
    exclude_patterns: list[str],
    root: pathlib.Path,
) -> dict:
    """Filter discovered YAML files by include/exclude glob patterns.

    Patterns are matched against repo-relative POSIX paths (e.g. 'zuul.d/jobs.yaml').
    If include_patterns is non-empty, a file must match at least one pattern to be kept.
    Files matching any exclude pattern are always dropped.
    """
    if not include_patterns and not exclude_patterns:
        return yaml_files_dict

    def should_include(path: pathlib.Path) -> bool:
        try:
            rel = path.relative_to(root).as_posix()
        except ValueError:
            rel = str(path)

        if include_patterns and not any(fnmatch.fnmatch(rel, pat) for pat in include_patterns):
            return False
        if exclude_patterns and any(fnmatch.fnmatch(rel, pat) for pat in exclude_patterns):
            return False
        return True

    return {key: [p for p in paths if should_include(p)] for key, paths in yaml_files_dict.items()}


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


def _route_by_severity(results: dict, rule_severities: dict) -> None:
    """Mutate results in-place to reflect configured per-rule severities.

    Moves findings between the errors and warnings buckets so that the
    existing print_results logic sees pre-routed counts.
    """
    # Promote default-warning checks to errors
    for rule, bucket in _RULE_WARNING_BUCKETS:
        if rule_severities.get(rule) == "error":
            count = len(results["warnings"][bucket])
            results["errors"]["promoted_warnings"] = (
                results["errors"].get("promoted_warnings", 0) + count
            )
            results["warnings"][bucket] = []

    # Demote default-error checks to warnings (display as duplicate-job-style entries)
    if rule_severities.get("check-duplicate-semaphore") == "warning":
        count = results["errors"]["duplicated_semaphores"]
        if count:
            results["warnings"]["duplicate_semaphores"].extend(["duplicate semaphore"] * count)
        results["errors"]["duplicated_semaphores"] = 0


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
    n_duplicate_semaphores = len(warnings["warnings"]["duplicate_semaphores"])
    n_playbook_paths = len(warnings["warnings"]["playbook_paths"])

    n_total = n_duplicate_jobs + n_nodeset + n_duplicate_semaphores + n_playbook_paths
    if n_bad_yaml == 0 and n_total == 0:
        return

    if severity == MsgSeverity.WARNING:
        zuul_utils.print_bold("Warnings", MsgSeverity.WARNING)
        print(f"Total {severity.value}s: {n_total}")

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

    if n_duplicate_semaphores:
        zuul_utils.print_bold(f"Duplicate semaphore {severity.value}s:", severity)
        zuul_utils.print_bold(f"Found {n_duplicate_semaphores} duplicate semaphores", None)
        for entry in warnings["warnings"]["duplicate_semaphores"]:
            print(f"{entry}")

    if n_playbook_paths:
        zuul_utils.print_bold(f"Invalid playbook path {severity.value}s:", severity)
        zuul_utils.print_bold(f"Found {n_playbook_paths} invalid playbook paths", None)
        for entry in warnings["warnings"]["playbook_paths"]:
            print(f"{entry}")


def print_results(
    results: dict,
    warnings_as_errors,
    ignore_warnings,
    *,
    rule_severities: dict | None = None,
) -> None:
    """Print the linting results.

    Args:
    ----
        results: A dictionary containing linting results.
        warnings_as_errors: A boolean indicating whether to handle warnings as errors.
        ignore_warnings: A boolean indicating whether to ignore warnings.
        rule_severities: Optional per-rule severity mapping from the loaded config.

    Returns:
    -------
        None.
    """
    if rule_severities:
        _route_by_severity(results, rule_severities)

    duplicated_jobs = results["warnings"]["duplicated_jobs"]
    inexistent_nodesets = results["warnings"]["inexistent_nodesets"]
    bad_yaml_files = results["warnings"]["bad_yaml_files"]
    total_semaphore_errors = results["errors"]["duplicated_semaphores"]
    total_yaml_errors = results["errors"]["yaml"]
    total_playbook_path_errors = results["errors"]["playbook_paths"]
    total_promoted = results["errors"].get("promoted_warnings", 0)
    total_warnings = len(bad_yaml_files) + len(duplicated_jobs) + len(inexistent_nodesets)
    total_errs = total_yaml_errors + total_playbook_path_errors + total_semaphore_errors + total_promoted
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
    if total_promoted:
        err_msg += f"\nPromoted warning errors: {total_promoted}"

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
    parser.add_argument(
        "--config",
        help="path to a zuulcilint config file (overrides auto-discovered configs)",
        default=None,
        metavar="PATH",
    )

    args = parser.parse_args()

    try:
        config = load_config(args.config)
    except (FileNotFoundError, ValueError) as exc:
        zuul_utils.print_bold(f"Config error: {exc}", MsgSeverity.ERROR)
        sys.exit(1)

    rule_severities: dict = config["rules"]
    # CLI --warnings-as-errors takes precedence; config value is the fallback.
    effective_wae: bool = args.warnings_as_errors or config.get("warnings-as-errors", False)

    schema = zuul_utils.get_zuul_schema(schema_file=args.schema)
    all_zuul_yaml_files = get_all_zuul_yaml_files(args.file)

    # Apply include/exclude glob filters from config (repo-relative POSIX paths).
    include_pats: list[str] = config.get("include", [])
    exclude_pats: list[str] = config.get("exclude", [])
    if include_pats or exclude_pats:
        # Warn when the user explicitly passed a file (not a directory) that
        # matches an exclude pattern — silently dropping it would be misleading.
        if exclude_pats:
            cwd = pathlib.Path.cwd()
            for raw in args.file:
                p = pathlib.Path(raw)
                if p.is_file():
                    try:
                        rel = p.relative_to(cwd).as_posix()
                    except ValueError:
                        rel = str(p)
                    if any(fnmatch.fnmatch(rel, pat) for pat in exclude_pats):
                        zuul_utils.print_bold(
                            f"warning: {rel} explicitly passed but matches an "
                            f"exclude pattern — skipping",
                            MsgSeverity.WARNING,
                        )

        all_zuul_yaml_files = _apply_file_filters(
            all_zuul_yaml_files,
            include_pats,
            exclude_pats,
            pathlib.Path.cwd(),
        )

    zuul_good_yaml = all_zuul_yaml_files["good_yaml"]
    zuul_bad_yaml = all_zuul_yaml_files["bad_yaml"]

    # Initialize results dictionary
    results = {
        "errors": {"duplicated_semaphores": 0, "playbook_paths": 0, "yaml": 0 },
        "warnings": {
            "duplicated_jobs": [],
            "inexistent_nodesets": [],
            "bad_yaml_files": zuul_bad_yaml,
            "duplicate_semaphores": [],
            "playbook_paths": [],
        },
    }

    # Lint all Zuul YAML files
    results["errors"]["yaml"] = lint_all_yaml_files(zuul_good_yaml, schema)

    # Check playbook paths.
    # Runs if the CLI flag is given OR if config explicitly enables it (non-disable severity).
    # CLI flag always wins: even if config says "disable", the flag forces the check to run
    # at "error" severity.
    sev_playbook = rule_severities.get("check-playbook-paths", "disable")
    run_playbook_check = args.check_playbook_paths or sev_playbook != "disable"
    # Effective severity: use config value; fall back to "error" when CLI flag forces the run.
    effective_playbook_sev = sev_playbook if sev_playbook != "disable" else "error"

    if run_playbook_check:
        zuul_utils.print_bold("Checking playbook paths", MsgSeverity.INFO)
        invalid_playbook_paths = lint_playbook_paths(zuul_good_yaml)
        if invalid_playbook_paths:
            if effective_playbook_sev == "warning":
                results["warnings"]["playbook_paths"].extend(
                    [f"invalid playbook path: {p}" for p in invalid_playbook_paths]
                )
            else:
                results["errors"]["playbook_paths"] = len(invalid_playbook_paths)
            zuul_utils.print_bold("Invalid playbook paths:", MsgSeverity.ERROR)
            for path in invalid_playbook_paths:
                print(f"{path}")
        else:
            print("No invalid playbook paths")

    # Check duplicated jobs (skip if disabled in config)
    if rule_severities.get("check-duplicated-jobs") != "disable":
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

    # Check for inexistent nodesets (skip if disabled in config)
    if rule_severities.get("check-inexistent-nodesets") != "disable":
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

    # Check for duplicate semaphore in job and job.run (skip if disabled in config)
    if rule_severities.get("check-duplicate-semaphore") != "disable":
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
        effective_wae,
        args.ignore_warnings,
        rule_severities=rule_severities,
    )


if __name__ == "__main__":
    main()
