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
            if isinstance(path, str):
                if not pathlib.Path(path).exists():
                    invalid_paths.append(path)
            if isinstance(path, dict):
                if "name" in path:
                    if not pathlib.Path(path["name"]).exists():
                        invalid_paths.append(path["name"])

    return invalid_paths


def check_duplicated_jobs(
    jobs: dict[pathlib.Path, list[dict | None]]
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
            try:
                if nodeset["name"] not in nodeset_list:
                    inexistent_nodesets.add(nodeset["name"])
            except TypeError:
                if (
                    job_nodeset_list.get("name", None)
                    and job_nodeset_list.get("name", None) not in nodeset_list
                ):
                    inexistent_nodesets.add(job_nodeset_list["name"])

    return inexistent_nodesets


def check_inexistent_secrets(
    secrets: list[dict],
    jobs: list[dict | None],
) -> list[dict[str, str]]:
    """
    Check that secret used by the existed job.

    Args:
    ----
        secrets: A list of secrets.
        jobs: A list of jobs.
    Returns:
    -------
        A list of inexistent secrets.
    """
    inexistent_secrets = set()
    job_secret = {}
    job_secrets_list = set()
    secret = {}
    secrets_list = set()

    for secret in secrets:
        secrets_list.add(secret["secret"]["name"])

    for job in jobs:
        try:
            if isinstance(job["job"]["secrets"], str):
                secret["name"] = job["job"]["secrets"]["secret"]
                job_secrets_list.add(secret)
        except KeyError:
            continue

        for job_secret in job_secrets_list:
            try:
                if secret["name"] not in secrets_list:
                    inexistent_secrets.add(secret["name"])
            except TypeError:
                if (
                    job_secrets_list.get("name", None)
                    and job_secrets_list.get("name", None) not in secrets_list
                ):
                    inexistent_secrets.add(job_secrets_list["name"])
    return inexistent_secrets
