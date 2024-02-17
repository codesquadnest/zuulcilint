"""Set of checker functions for Zuul Lint."""

from __future__ import annotations

import pathlib


def check_job_playbook_paths(
    job: dict[str, str | list[str] | None],
) -> list[str]:
    """Check that all playbooks in a job have a valid path.

    Args:
    ----
        job: A dictionary representing a Zuul job.

    Returns:
    -------
        A list of invalid playbook paths.
    """
    invalid_paths = []

    for key in ["pre-run", "run", "post-run"]:
        paths = job.get(key)
        if isinstance(paths, list):
            invalid_paths.extend(path for path in paths if not pathlib.Path(path).is_file())
        elif paths and not pathlib.Path(paths).is_file():
            invalid_paths.append(paths)

    return invalid_paths


def check_duplicated_jobs(
    jobs: list[list[dict[str, str] | None]],
) -> set[dict[str, str] | None]:
    """Check that all jobs are unique in different Zuul YAML files.

    Args:
    ----
        jobs: A list of lists of dictionaries representing Zuul jobs.

    Returns:
    -------
        A set of duplicated jobs.
    """
    seen_items = set()
    duplicated_items = set()
    unique_items = set()

    for sublist in jobs:
        sublist_set = set(sublist)
        for job in sublist_set:
            if job in seen_items:
                duplicated_items.add(job)
            seen_items.add(job)
        unique_items.update(sublist_set)

    return duplicated_items


def get_all_project_secrets(
    secrets: list[dict],
) -> list[dict[str, str]]:
    """
    Get all encrypted secrets.

    Args:
    ----
        secrets: A list of secrets.
    Returns:
    -------
        A list of encrypted secrets.
    """

    # TODO: This function need improvement

    secrets_list = set()
    for secret in secrets:
        secrets_list.add(secret["secret"]["name"])
        try:
            secret_list = secrets["secret"]["data"]
        except KeyError:
            continue
        for secret in secret_list:
            if "!encrypted/pkcs1-oaep" not in secret["secret"]["name"][secret]:
                print("Error: The secret don't use the Zuul encryption scheme")
                sys.exit(1)

    return secrets_list


def check_inexistent_secrets(
    secrets: list[dict],
    jobs: list[dict | None],
) -> list[dict[str, str]]:
    """
    Check that secret used by the job exist.

    Args:
    ----
        secrets: A list of secrets.
        jobs: A list of jobs.
    Returns:
    -------
        A list of inexistent secrets.
    """
    inexistent_secrets = set()
    job_secrets_list = set()
    secret = {}

    for job in jobs:
        try:
            if isinstance(job["job"]["secrets"], str):
                secret["name"] = job["job"]["secrets"]["secret"]
                job_secrets_list.add(secret)
        except KeyError:
            continue
    return inexistent_secrets
