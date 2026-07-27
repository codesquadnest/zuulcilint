"""Set of checker functions for Zuul Lint."""

from __future__ import annotations

import pathlib


def check_job_playbook_paths(job: dict[str, dict | list[str | dict]]) -> list[str]:
    """Check that all playbooks in a job have a valid path.

    Args:
    ----
        job: A dictionary containing a Zuul job.

    Returns:
    -------
        A list of invalid playbook paths.

    """
    invalid_paths = []

    for key in ["pre-run", "run", "post-run", "cleanup-run"]:
        paths = job.get(key)
        if paths is None:
            continue

        # Convert to list if it's a single object
        if not isinstance(paths, list):
            paths = [paths]

        for path in paths:
            if isinstance(path, str) and not pathlib.Path(path).exists():
                invalid_paths.append(path)
            if (
                isinstance(path, dict)
                and "name" in path
                and not pathlib.Path(path["name"]).exists()
            ):
                invalid_paths.append(path["name"])

    return invalid_paths


def check_duplicated_jobs(
    jobs: dict[pathlib.Path, list[dict | None]],
) -> set[dict[str, str] | None]:
    """Check that all jobs are unique in different Zuul YAML files.

    Args:
    ----
        jobs: A dictionary containing a list of Zuul jobs.

    Returns:
    -------
        A set of duplicated jobs.

    """
    seen_items = set()
    duplicated_items = set()
    unique_items = set()

    for joblist in jobs.values():
        try:
            sublist_set = {job["job"]["name"] for job in joblist}
        except KeyError:
            continue
        for job in sublist_set:
            if job in seen_items:
                duplicated_items.add(job)
            seen_items.add(job)
        unique_items.update(sublist_set)

    return duplicated_items


def _collect_known_nodeset_names(nodesets: list[dict]) -> set[str]:
    """Collect the names of all defined nodesets and their nodes."""
    nodeset_list = set()
    for nodeset in nodesets:
        nodeset_list.add(nodeset["nodeset"]["name"])
        try:
            node_list = nodeset["nodeset"]["nodes"]
        except KeyError:
            continue
        for node in node_list:
            if isinstance(node["name"], str):
                nodeset_list.add(node["name"])
            if isinstance(node["name"], list):
                for node_name in node["name"]:
                    nodeset_list.add(node_name)
    return nodeset_list


def _job_nodesets(job: dict) -> list[dict] | None:
    """Return the nodeset entries referenced by a job, or None if it has none."""
    try:
        if isinstance(job["job"]["nodeset"], str):
            return [{"name": job["job"]["nodeset"]}]
        return job["job"]["nodeset"]["nodes"]
    except KeyError:
        return None


def _record_inexistent_nodeset(
    nodeset: dict | str,
    job_nodesets: list[dict] | dict,
    nodeset_list: set[str],
    inexistent_nodesets: set[str],
) -> None:
    """Add nodeset's name to inexistent_nodesets if it isn't a known nodeset."""
    try:
        if nodeset["name"] not in nodeset_list:
            inexistent_nodesets.add(nodeset["name"])
    except TypeError:
        name = job_nodesets.get("name", None)
        if name and name not in nodeset_list:
            inexistent_nodesets.add(job_nodesets["name"])


def check_inexistent_nodesets(
    nodesets: list[dict],
    jobs: list[dict | None],
) -> list[dict[str, str]]:
    """Check that all used nodesets exist.

    Args:
    ----
        nodesets: A list of nodesets.
        jobs: A list of Zuul jobs.

    Returns:
    -------
        A list of inexistent nodesets.

    """
    nodeset_list = _collect_known_nodeset_names(nodesets)
    inexistent_nodesets = set()

    for job in jobs:
        job_nodesets = _job_nodesets(job)
        if job_nodesets is None:
            continue
        for nodeset in job_nodesets:
            _record_inexistent_nodeset(nodeset, job_nodesets, nodeset_list, inexistent_nodesets)

    return inexistent_nodesets


def check_duplicate_semaphore(jobs: list[dict | None]) -> set[dict[str, str] | None]:
    """Check for jobs and their run entries sharing a semaphore with the same name.

    Args:
    ----
        jobs: A list of Zuul jobs.

    Returns:
    -------
        A set of duplicated semaphores.

    """
    duplicate_semaphores = set()
    _job_semaphore_list = {}
    _run_semaphore_list = {}

    for job in jobs:
        if job is None or "job" not in job:
            continue

        job_name = job["job"].get("name")
        if job_name is None:
            continue

        # Initialize lists for semaphores if not already present
        _job_semaphore_list.setdefault(job_name, [])
        _run_semaphore_list.setdefault(job_name, [])

        # Collect job semaphores
        job_semaphores = job["job"].get("semaphores", [])
        if isinstance(job_semaphores, str):
            _job_semaphore_list[job_name].append(job_semaphores)
        else:
            _job_semaphore_list[job_name].extend(job_semaphores)

        # Collect run semaphores
        if isinstance(job["job"].get("run"), str):
            continue
        run_entries = job["job"].get("run", [])
        if isinstance(run_entries, dict):  # Single run entry case
            run_entries = [run_entries]
        for run in run_entries:
            if isinstance(run, str):
                # When run entry is a string this means it's a playbook
                continue
            run_semaphores = run.get("semaphores", [])
            if isinstance(run_semaphores, str):
                _run_semaphore_list[job_name].append(run_semaphores)
            else:
                _run_semaphore_list[job_name].extend(run_semaphores)

    # Find duplicate semaphores
    for job_name, job_semaphores in _job_semaphore_list.items():
        job_semaphores_set = set(job_semaphores)
        run_semaphores_set = set(_run_semaphore_list[job_name])
        duplicate_semaphores.update(job_semaphores_set & run_semaphores_set)

    return duplicate_semaphores
