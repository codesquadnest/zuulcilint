"""Set of utility functions for Zuul Lint."""

from __future__ import annotations

import json
import pathlib
import sys
from collections import defaultdict

import yaml


def get_zuul_schema(schema_file: str) -> dict:
    """Load the Zuul schema from a JSON file.

    Args:
    ----
        schema_file: The path to the JSON schema file.

    Returns:
    -------
        A dictionary representing the Zuul schema.
    """
    try:
        with pathlib.Path.open(schema_file, encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        print(f"Schema file not found: {schema_file}", file=sys.stderr)
        sys.exit(1)
    except json.JSONDecodeError:
        print(f"Invalid JSON in schema file: {schema_file}", file=sys.stderr)
        sys.exit(1)


def get_zuul_yaml_files(path: pathlib.Path) -> dict[str, list[pathlib.Path]]:
    """Retrieve a dictionary of Zuul YAML/YML files from the specified path.

    Args:
    ----
        path (Path): The path to search for Zuul YAML files.

    Returns:
    -------
        dict[str, List[Path]]: A dictionary containing the keys 'good_yaml'(.yaml) and
        'bad_yaml'(.yml), where values are lists containing the Path objects for each
        of the file extensions found.
    """
    zuul_yaml_files = defaultdict(list)

    if(path.is_file()):
        if path.suffix == ".yaml":
            zuul_yaml_files["good_yaml"].append(path)
        elif path.suffix == ".yml":
            zuul_yaml_files["bad_yaml"].append(path)
    elif(path.is_dir()):
        for p in path.iterdir():
            for file_type, yaml_file_path in get_zuul_yaml_files(p).items():
                zuul_yaml_files[file_type].extend(yaml_file_path)

    else:
        print(f"Skipping {path}")

    return zuul_yaml_files


def get_jobs_from_zuul_yaml(zuul_yaml_file: str) -> list[dict[str, str] | None]:
    """Retrieve a list of Zuul jobs from the specified YAML file.

    Args:
    ----
        zuul_yaml_file: The path to the YAML file to search for Zuul jobs.

    Returns:
    -------
        A list of dictionaries representing the Zuul jobs found.
    """
    try:
        with pathlib.Path.open(zuul_yaml_file, encoding="utf-8") as f:
            return [job for job in yaml.safe_load(f) if job.get("job")]
    except FileNotFoundError:
        print(f"Zuul YAML file not found: {zuul_yaml_file}", file=sys.stderr)
        sys.exit(1)
    except yaml.YAMLError:
        print(f"Invalid YAML in Zuul YAML file: {zuul_yaml_file}", file=sys.stderr)
        sys.exit(1)


def get_playbook_paths_from_job(job: dict[str, str] | None) -> list[str | None]:
    """Retrieve a list of playbook paths from the specified job.

    Args:
    ----
        job: A dictionary representing a Zuul job.

    Returns:
    -------
        A list of playbook paths.
    """
    path_keys = ["pre-run", "run", "post-run"]

    return [job.get(key) for key in path_keys if job.get(key)]


def get_files_with_extension(path: str, extension: str) -> list[pathlib.Path]:
    """Get files with provided extension from provided path and it's subdirectories.

    Args:
    ----
        path: path to directory to search
        extension: file extension to search for

    Returns:
    -------
        A list of files with provided extension.
    """
    return list(pathlib.Path(path).rglob(f"*.{extension}"))


def encrypted_pkcs1_oaep_constructor(loader: str, node: str) -> str:
    """Handle encrypted strings in YAML files.

    Args:
    ----
        loader: The YAML loader.
        node: The YAML node.

    Returns:
    -------
        The decrypted string.
    """
    if isinstance(node, yaml.ScalarNode):
        # Handle scalar node
        return loader.construct_scalar(node)
    if isinstance(node, yaml.SequenceNode):
        # Handle sequence node
        return loader.construct_sequence(node)

    # Handle other node types if needed
    raise yaml.constructor.ConstructorError(
        None,
        None,
        "invalid node type: '%s'" % type(node),
        node.start_mark,
    )


def print_bold(msg: str, msg_type: str) -> None:
    """Print a bold message.

    Args:
    ----
        msg: The message to print.
        msg_type: The type of message to print.

    Returns:
    -------
        None.
    """
    if msg_type == "error":
        print(f"\n\33[1;49;31m{msg}\33[0m", file=sys.stderr)
    elif msg_type == "warning":
        print(f"\n\33[1;49;33m{msg}\33[0m")
    elif msg_type == "info":
        print(f"\n\33[1;49;34m{msg}\33[0m")
    elif msg_type == "success":
        print(f"\n\33[1;49;32m{msg}\33[0m")
    else:
        print(f"\33[1;49;37m{msg}\33[0m")
