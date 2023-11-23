"""Zuul Linter Tests.

This module contains tests for the Zuul Linter utils module.
"""
import pathlib
import tempfile

import pytest

import zuullint.utils as zuullint_utils


def setup_tmp_list_of_files():
    """Create a temporary directory with a list of files.

    Returns
    -------
        A Path object representing the temporary directory.
    """
    tmp_path = pathlib.Path(tempfile.mkdtemp())
    for i in range(2):
        with pathlib.Path.open(tmp_path / f"file{i}.yaml", "w", encoding="utf-8") as f:
            f.write("hello")
    return tmp_path


def setup_zuul_job_yaml():
    """Create a temporary directory with a list of files.

    Returns
    -------
        A Path object representing the temporary directory.
    """
    tmp_path = pathlib.Path(tempfile.mkdtemp())
    with pathlib.Path.open(tmp_path / "job.yaml", "w", encoding="utf-8") as f:
        f.write(
            """
            - job:
                name: test-job
                pre-run: playbooks/pre-run.yaml
                run: playbooks/run.yaml
                post-run: playbooks/post-run.yaml
            """,
        )
    return tmp_path


def test_get_schema_valid():
    """Test that get_schema() returns a valid schema."""
    tmp_schema = pathlib.Path(tempfile.mkstemp()[1])
    with pathlib.Path.open(tmp_schema, "w", encoding="utf-8") as f:
        f.write("{}")
    assert zuullint_utils.get_zuul_schema(tmp_schema) == {}


def test_get_schema_file_not_found():
    """Test that get_schema() exits when the schema file is not found."""
    tmp_schema = pathlib.Path(tempfile.mkstemp()[1])
    tmp_schema.unlink()
    try:
        zuullint_utils.get_zuul_schema(tmp_schema)
    except SystemExit:
        pytest.raises(FileNotFoundError)


def test_get_schema_invalid_json():
    """Test that get_schema() exits when the schema file is invalid."""
    tmp_schema = pathlib.Path(tempfile.mkstemp()[1])
    with pathlib.Path.open(tmp_schema, "w", encoding="utf-8") as f:
        f.write("{- foo = bar}")
        with pytest.raises(SystemExit):
            zuullint_utils.get_zuul_schema(tmp_schema)


def test_get_zuul_yaml_files_find():
    """Test that get_zuul_yaml_files() finds files."""
    tmp_path = setup_tmp_list_of_files()
    default_len = 2
    zuul_yaml_files = [
        file.name for file in zuullint_utils.get_zuul_yaml_files(tmp_path)
    ]
    assert len(zuul_yaml_files) == default_len
    assert "file0.yaml" in zuul_yaml_files
    assert "file1.yaml" in zuul_yaml_files

    tmp_path = tmp_path / "subdir"
    tmp_path.mkdir()
    assert len(zuullint_utils.get_zuul_yaml_files(tmp_path)) == 0

    assert len(zuullint_utils.get_zuul_yaml_files(tmp_path / "invalid_path")) == 0


def test_get_zuul_yaml_files_skip():
    """Test that get_zuul_yaml_files() skips files."""
    tmp_path = setup_tmp_list_of_files()
    tmp_path = tmp_path / "subdir"
    tmp_path.mkdir()
    tmp_path = tmp_path / "file2.yaml"
    with pathlib.Path.open(tmp_path, "w", encoding="utf-8") as f:
        f.write("hello")
    assert len(zuullint_utils.get_zuul_yaml_files(tmp_path)) == 1

    tmp_path = tmp_path.parent / "file3.yml"
    with pathlib.Path.open(tmp_path, "w", encoding="utf-8") as f:
        f.write("hello")
    assert len(zuullint_utils.get_zuul_yaml_files(tmp_path)) == 0


def test_get_jobs_from_zuul_yaml():
    """Test that get_jobs_from_zuul_yaml() returns a list of jobs."""
    tmp_path = setup_zuul_job_yaml()
    jobs = zuullint_utils.get_jobs_from_zuul_yaml(tmp_path / "job.yaml")
    assert len(jobs) == 1
    assert jobs[0]["job"]["name"] == "test-job"


def test_get_jobs_from_zuul_yaml_invalid_yaml():
    """Test exits when the YAML is invalid."""
    tmp_path = setup_zuul_job_yaml()
    with pathlib.Path.open(tmp_path / "job.yaml", "w", encoding="utf-8") as f:
        f.write("{- foo = bar}")
    with pytest.raises(SystemExit):
        zuullint_utils.get_jobs_from_zuul_yaml(tmp_path / "job.yaml")


def test_get_jobs_from_zuul_yaml_no_jobs():
    """Test return an empty list when no jobs are found."""
    tmp_path = setup_zuul_job_yaml()
    with pathlib.Path.open(tmp_path / "job.yaml", "w", encoding="utf-8") as f:
        f.write(
            """
            - pipeline:
                name: test-pipeline
            """,
        )
    assert len(zuullint_utils.get_jobs_from_zuul_yaml(tmp_path / "job.yaml")) == 0


def test_get_jobs_from_zuul_yaml_no_file():
    """Test return an empty list when no file is found."""
    tmp_path = setup_zuul_job_yaml()
    try:
        zuullint_utils.get_jobs_from_zuul_yaml(tmp_path / "invalid_file")
    except SystemExit:
        pytest.raises(FileNotFoundError)


def test_get_playbook_paths_from_job():
    """Test that get_playbook_paths_from_job() returns a list of playbook paths."""
    tmp_path = setup_zuul_job_yaml()
    jobs = zuullint_utils.get_jobs_from_zuul_yaml(tmp_path / "job.yaml")
    playbook_paths = zuullint_utils.get_playbook_paths_from_job(jobs[0].get("job"))
    size = 3
    assert len(playbook_paths) == size
    assert playbook_paths[0] == "playbooks/pre-run.yaml"
    assert playbook_paths[1] == "playbooks/run.yaml"
    assert playbook_paths[2] == "playbooks/post-run.yaml"


def test_get_playbook_paths_from_job_no_playbook_paths():
    """Test return an empty list when no playbook paths are found."""
    tmp_path = setup_zuul_job_yaml()
    with pathlib.Path.open(tmp_path / "job.yaml", "w", encoding="utf-8") as f:
        f.write(
            """
            - job:
                name: test-job
            """,
        )
    jobs = zuullint_utils.get_jobs_from_zuul_yaml(tmp_path / "job.yaml")
    playbook_paths = zuullint_utils.get_playbook_paths_from_job(jobs[0].get("job"))
    assert len(playbook_paths) == 0


def test_get_files_with_extension():
    """Test return a list of files with the specified extension."""
    tmp_path = setup_tmp_list_of_files()
    files = zuullint_utils.get_files_with_extension(tmp_path, "yaml")
    size = 2
    assert len(files) == size
