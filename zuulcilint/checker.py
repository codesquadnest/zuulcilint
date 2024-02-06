"""Set of checker functions for Zuul Lint."""

from __future__ import annotations

import pathlib


def check_job_playbook_paths(
    job: list[dict[str, str | list[str]] | None],
) -> list[str]:
    """Check that all playbooks in a job have a valid path.

    Args:
    ----
        job: A list of Zuul jobs.

    Returns:
    -------
        A list of invalid playbook paths.
    """
    invalid_paths = []

    for key in ["pre-run", "run", "post-run"]:
        paths = job.get(key)
        if isinstance(paths, list):
            for path in paths:
                if isinstance(path, str):
                    if not pathlib.Path(path).exists():
                        invalid_paths.append(path)
                if isinstance(path, dict):
                    for key, val in path.items():
                        if key == "name":
                            if not pathlib.Path(val).exists():
                                invalid_paths.append(val)
        if isinstance(paths, str):
            if not pathlib.Path(paths).exists():
                invalid_paths.append(paths)

    return invalid_paths


def check_duplicated_jobs(
    jobs: dict[pathlib.Path, list[dict | None]]
) -> set[dict[str, str] | None]:
    """Check that all jobs are unique in different Zuul YAML files.

    Args:
    ----
        jobs: A list of Zuul jobs.

    Returns:
    -------
        A set of duplicated jobs.
    """
    seen_items = set()
    duplicated_items = set()
    unique_items = set()

    for joblist in jobs.values():
        try:
            sublist_set = set(job["job"]["name"] for job in joblist)
        except KeyError:
            continue
        for job in sublist_set:
            if job in seen_items:
                duplicated_items.add(job)
            seen_items.add(job)
        unique_items.update(sublist_set)

    return duplicated_items


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
    inexistent_nodesets = set()

    for job in jobs:
        try:
            if isinstance(job["job"]["nodeset"], str):
                nodeset = {}
                nodeset["name"] = job["job"]["nodeset"]
                job_nodeset_list = [nodeset]
            else:
                job_nodeset_list = job["job"]["nodeset"]["nodes"]
        except KeyError:
            continue
        for nodeset in job_nodeset_list:
            if nodeset["name"] not in nodeset_list:
                inexistent_nodesets.add(nodeset["name"])

    return inexistent_nodesets
