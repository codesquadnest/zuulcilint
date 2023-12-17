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
            invalid_paths.extend(
                path for path in paths if not pathlib.Path(path).is_file()
            )
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
