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
from zuulcilint.config import DEFAULT_RULES, load_config
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
        return not (exclude_patterns and any(fnmatch.fnmatch(rel, pat) for pat in exclude_patterns))

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


def print_warnings(
    results: dict,
    rule_severities: dict,
    severity: MsgSeverity = MsgSeverity.WARNING,
) -> None:
    """Print findings that are routed to warning severity.

    Args:
    ----
        results: A flat dictionary of per-rule findings.
        rule_severities: Per-rule severity mapping from the loaded config.
        severity: Display severity (WARNING normally, ERROR when warnings-as-errors).

    Returns:
    -------
        None.

    """
    n_bad_yaml = len(results["bad_yaml_files"])

    # Only include rule findings configured at "warning" severity.
    n_duplicate_jobs = (
        len(results["duplicated_jobs"])
        if rule_severities.get("check-duplicated-jobs") == "warning"
        else 0
    )
    n_nodeset = (
        len(results["inexistent_nodesets"])
        if rule_severities.get("check-inexistent-nodesets") == "warning"
        else 0
    )
    n_duplicate_semaphores = (
        len(results["duplicate_semaphores"])
        if rule_severities.get("check-duplicate-semaphore") == "warning"
        else 0
    )
    n_playbook_paths = (
        len(results["playbook_paths"])
        if rule_severities.get("check-playbook-paths") == "warning"
        else 0
    )

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
        for file_path in results["bad_yaml_files"]:
            print(f"{file_path}")

    if n_duplicate_jobs:
        zuul_utils.print_bold(f"Duplicate job {severity.value}s:", severity)
        zuul_utils.print_bold(f"Found {n_duplicate_jobs} duplicate jobs", None)
        for job in results["duplicated_jobs"]:
            print(f"{job}")

    if n_nodeset:
        zuul_utils.print_bold(f"Inexistent nodeset {severity.value}s:", severity)
        zuul_utils.print_bold(f"Found {n_nodeset} inexistent nodesets", None)
        for nodeset in results["inexistent_nodesets"]:
            print(f"{nodeset}")

    if n_duplicate_semaphores:
        zuul_utils.print_bold(f"Duplicate semaphore {severity.value}s:", severity)
        zuul_utils.print_bold(f"Found {n_duplicate_semaphores} duplicate semaphores", None)
        for entry in results["duplicate_semaphores"]:
            print(f"{entry}")

    if n_playbook_paths:
        zuul_utils.print_bold(f"Invalid playbook path {severity.value}s:", severity)
        zuul_utils.print_bold(f"Found {n_playbook_paths} invalid playbook paths", None)
        for entry in results["playbook_paths"]:
            print(f"{entry}")


def _resolve_rule_severities(rule_severities: dict) -> dict[str, str]:
    """Resolve effective severity for each configurable rule, falling back to defaults."""
    return {rule: rule_severities.get(rule, default) for rule, default in DEFAULT_RULES.items()}


def _rule_counts(results: dict) -> dict[str, int]:
    """Map each configurable rule to its finding count in results."""
    return {
        "check-duplicated-jobs": len(results["duplicated_jobs"]),
        "check-inexistent-nodesets": len(results["inexistent_nodesets"]),
        "check-duplicate-semaphore": len(results["duplicate_semaphores"]),
        "check-playbook-paths": len(results["playbook_paths"]),
    }


def _count_at_severity(counts: dict[str, int], severities: dict[str, str], target: str) -> int:
    """Sum finding counts for rules whose effective severity matches target."""
    return sum(count for rule, count in counts.items() if severities[rule] == target)


def _build_extra_message(
    counts: dict[str, int],
    severities: dict[str, str],
    n_bad_yaml: int,
) -> str:
    """Build the warnings-as-errors detail message appended to the failure summary."""
    extra_msg = ""
    if n_bad_yaml:
        extra_msg += f"\nFile extension errors: {n_bad_yaml}"
    if severities["check-duplicated-jobs"] == "warning" and counts["check-duplicated-jobs"]:
        extra_msg += f"\nDuplicated jobs errors: {counts['check-duplicated-jobs']}"
    if severities["check-inexistent-nodesets"] == "warning" and counts["check-inexistent-nodesets"]:
        extra_msg += f"\nInexistent nodesets errors: {counts['check-inexistent-nodesets']}"
    return extra_msg


def _build_error_message(
    total_errs: int,
    counts: dict[str, int],
    severities: dict[str, str],
    n_yaml_errors: int,
) -> str:
    """Build the failure summary message."""
    err_msg = f"Total errors: {total_errs}\n"

    if severities["check-duplicate-semaphore"] == "error" and counts["check-duplicate-semaphore"]:
        err_msg += f"Duplicated semaphores: {counts['check-duplicate-semaphore']}"
    if severities["check-playbook-paths"] == "error" and counts["check-playbook-paths"]:
        err_msg += f"\nPlaybook path errors: {counts['check-playbook-paths']}"
    if n_yaml_errors:
        err_msg += f"\nYAML validation errors: {n_yaml_errors}"

    # Findings from default-warning rules promoted to error via config.
    n_promoted = 0
    if severities["check-duplicated-jobs"] == "error":
        n_promoted += counts["check-duplicated-jobs"]
    if severities["check-inexistent-nodesets"] == "error":
        n_promoted += counts["check-inexistent-nodesets"]
    if n_promoted:
        err_msg += f"\nPromoted warning errors: {n_promoted}"

    return err_msg


def print_results(
    results: dict,
    warnings_as_errors,
    ignore_warnings,
    *,
    rule_severities: dict,
) -> None:
    """Print the linting results.

    Args:
    ----
        results: A flat dictionary of per-rule findings.
        warnings_as_errors: A boolean indicating whether to handle warnings as errors.
        ignore_warnings: A boolean indicating whether to ignore warnings.
        rule_severities: Per-rule severity mapping from the loaded config.

    Returns:
    -------
        None.

    """
    severities = _resolve_rule_severities(rule_severities)
    counts = _rule_counts(results)
    n_yaml_errors = results["yaml_schema_errors"]
    n_bad_yaml = len(results["bad_yaml_files"])

    # Findings at "error" severity contribute to the error count; "warning"
    # severity (plus bad_yaml_files, which is always a warning) to the warning count.
    total_errs = n_yaml_errors + _count_at_severity(counts, severities, "error")
    total_warnings = n_bad_yaml + _count_at_severity(counts, severities, "warning")

    extra_msg = ""
    # --warnings-as-errors flag has higher precedence than --ignore-warnings.
    if warnings_as_errors:
        total_errs += total_warnings
        extra_msg = _build_extra_message(counts, severities, n_bad_yaml)
        print_warnings(results=results, rule_severities=rule_severities, severity=MsgSeverity.ERROR)
    elif not ignore_warnings:
        print_warnings(results=results, rule_severities=rule_severities)

    if total_errs == 0:
        zuul_utils.print_bold("Passed", MsgSeverity.SUCCESS)
        sys.exit(0)

    zuul_utils.print_bold("Failed", MsgSeverity.ERROR)
    err_msg = _build_error_message(total_errs, counts, severities, n_yaml_errors)
    zuul_utils.print_bold(f"{err_msg + extra_msg}", MsgSeverity.ERROR)
    sys.exit(1)


def _build_arg_parser() -> argparse.ArgumentParser:
    """Build the zuulcilint command-line argument parser."""
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
    return parser


def _warn_excluded_explicit_files(files: list[str], exclude_pats: list[str]) -> None:
    """Warn when an explicitly passed file (not a directory) matches an exclude pattern.

    Silently dropping it would be misleading.
    """
    cwd = pathlib.Path.cwd()
    for raw in files:
        p = pathlib.Path(raw)
        if not p.is_file():
            continue
        try:
            rel = p.relative_to(cwd).as_posix()
        except ValueError:
            rel = str(p)
        if any(fnmatch.fnmatch(rel, pat) for pat in exclude_pats):
            zuul_utils.print_bold(
                f"warning: {rel} explicitly passed but matches an exclude pattern — skipping",
                MsgSeverity.WARNING,
            )


def _run_playbook_check(
    zuul_good_yaml: list[pathlib.Path],
    *,
    check_playbook_paths: bool,
    rule_severities: dict,
) -> tuple[list[str], dict]:
    """Run the playbook-path check if enabled.

    Runs if the CLI flag is given OR if config explicitly enables it (non-disable
    severity). The CLI flag always wins: even if config says "disable", the flag
    forces the check to run at "error" severity.

    Returns the findings and the (possibly overridden) rule severities.
    """
    default_playbook_sev = DEFAULT_RULES["check-playbook-paths"]
    sev_playbook = rule_severities.get("check-playbook-paths", default_playbook_sev)
    run_check = check_playbook_paths or sev_playbook != "disable"
    if check_playbook_paths and sev_playbook == "disable":
        rule_severities = dict(rule_severities)
        rule_severities["check-playbook-paths"] = "error"

    if not run_check:
        return [], rule_severities

    zuul_utils.print_bold("Checking playbook paths", MsgSeverity.INFO)
    invalid_playbook_paths = lint_playbook_paths(zuul_good_yaml)
    if not invalid_playbook_paths:
        print("No invalid playbook paths")
        return [], rule_severities

    zuul_utils.print_bold("Invalid playbook paths:", MsgSeverity.ERROR)
    for path in invalid_playbook_paths:
        print(f"{path}")
    return [f"invalid playbook path: {p}" for p in invalid_playbook_paths], rule_severities


def _run_duplicated_jobs_check(zuul_good_yaml: list[pathlib.Path], rule_severities: dict):
    """Run the duplicated-jobs check, skipping it if disabled in config."""
    if rule_severities.get("check-duplicated-jobs") == "disable":
        return []

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
    return duplicated_jobs


def _run_inexistent_nodesets_check(zuul_good_yaml: list[pathlib.Path], rule_severities: dict):
    """Run the inexistent-nodesets check, skipping it if disabled in config."""
    if rule_severities.get("check-inexistent-nodesets") == "disable":
        return []

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
    return inexistent_nodesets


def _run_duplicate_semaphore_check(
    zuul_good_yaml: list[pathlib.Path],
    rule_severities: dict,
) -> list:
    """Run the duplicate-semaphore check, skipping it if disabled in config."""
    if rule_severities.get("check-duplicate-semaphore") == "disable":
        return []

    zuul_utils.print_bold("Checking for duplicate semaphore", MsgSeverity.INFO)
    duplicate_semaphore = zuul_checker.check_duplicate_semaphore(
        get_all_zuul_objects_by_type(zuul_good_yaml, ZuulObject.JOB),
    )
    if duplicate_semaphore:
        for semaphore in duplicate_semaphore:
            print(f"{semaphore}")
    else:
        print("No duplicate semaphore found")
    return list(duplicate_semaphore)


def main(argv: list[str] | None = None):
    """Parse command-line arguments and run the Zuul linter on the specified file(s).

    Args:
    ----
        argv: Optional list of arguments. Defaults to sys.argv[1:] when None.

    Returns:
    -------
        None.

    """
    args = _build_arg_parser().parse_args(argv)

    try:
        config = load_config(args.config)
    except (FileNotFoundError, TypeError, ValueError) as exc:
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
        if exclude_pats:
            _warn_excluded_explicit_files(args.file, exclude_pats)
        all_zuul_yaml_files = _apply_file_filters(
            all_zuul_yaml_files,
            include_pats,
            exclude_pats,
            pathlib.Path.cwd(),
        )

    zuul_good_yaml = all_zuul_yaml_files.get("good_yaml", [])
    zuul_bad_yaml = all_zuul_yaml_files.get("bad_yaml", [])

    # Flat results dict — findings stored per-rule, severity applied at display time.
    results = {
        "yaml_schema_errors": 0,
        "bad_yaml_files": zuul_bad_yaml,
        "duplicated_jobs": [],
        "inexistent_nodesets": [],
        "duplicate_semaphores": [],
        "playbook_paths": [],
    }

    # Lint all Zuul YAML files
    results["yaml_schema_errors"] = lint_all_yaml_files(zuul_good_yaml, schema)

    results["playbook_paths"], rule_severities = _run_playbook_check(
        zuul_good_yaml,
        check_playbook_paths=args.check_playbook_paths,
        rule_severities=rule_severities,
    )
    results["duplicated_jobs"] = _run_duplicated_jobs_check(zuul_good_yaml, rule_severities)
    results["inexistent_nodesets"] = _run_inexistent_nodesets_check(
        zuul_good_yaml,
        rule_severities,
    )
    results["duplicate_semaphores"] = _run_duplicate_semaphore_check(
        zuul_good_yaml,
        rule_severities,
    )

    print_results(
        results,
        effective_wae,
        args.ignore_warnings,
        rule_severities=rule_severities,
    )


if __name__ == "__main__":
    main()
