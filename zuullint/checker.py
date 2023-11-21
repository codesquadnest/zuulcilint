"""Set of checker functions for Zuul Lint."""

from __future__ import annotations

import pathlib


def check_job_playbook_paths(job: dict[str, str] | None) -> list[str | None]:
    """Check that all playbooks in a job have a valid path.

    Args:
    ----
        job: A dictionary representing a Zuul job.

    Returns:
    -------
        A list of invalid playbook paths.
    """
    path_keys = ["pre-run", "run", "post-run"]

    invalid_paths = []

    invalid_paths.extend(
        [
            path
            for key in path_keys
            if (path := job.get(key)) and not pathlib.Path(path).is_file()
        ],
    )
    return invalid_paths
