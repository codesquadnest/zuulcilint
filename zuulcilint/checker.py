"""Set of checker functions for Zuul Lint."""

from __future__ import annotations

import pathlib
from typing import Dict, List, Set, Union


def check_job_playbook_paths(
    job: Dict[str, Union[str, List[str]]] | None
) -> List[Union[str, None]]:
    """Check that all playbooks in a job have a valid path.

    Args:
    ----
        job: A dictionary representing a Zuul job.

    Returns:
    -------
        A list of invalid playbook paths.
    """
    invalid_paths: List[Union[str, None]] = []

    for key in ["pre-run", "run", "post-run"]:
        paths = job.get(key)
        if isinstance(paths, list):
            invalid_paths.extend(path for path in paths if not pathlib.Path(path).is_file())
        elif paths and not pathlib.Path(paths).is_file():
            invalid_paths.append(paths)

    return invalid_paths


def check_repeated_jobs(
    jobs: List[List[Dict[str, str] | None]]
) -> Set[Dict[str, str] | None]:
    """Check that all jobs are unique in different Zuul YAML files.

    Args:
        jobs: A list of lists of dictionaries representing Zuul jobs.

    Returns:
        A set of repeated jobs.
    """

    seen_items = set()
    repeated_items = set()
    unique_items = set()

    for sublist in jobs:
        sublist_set = set(sublist)
        for job in sublist_set:
            if job in seen_items:
                repeated_items.add(job)
            seen_items.add(job)
        unique_items.update(sublist_set)

    return repeated_items
