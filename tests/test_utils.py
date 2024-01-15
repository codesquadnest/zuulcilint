"""Zuul Linter Tests.

This module contains tests for the Zuul Linter utils module.
"""
import pathlib
import tempfile

import pytest

import zuulcilint.utils as zuulcilint_utils
from zuulcilint.utils import ZuulObject


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


def setup_zuul_obj_yaml(obj_type: ZuulObject):
    """Create a temporary directory with a list of files.

    Returns
    -------
        A Path object representing the temporary directory.
    """
    tmp_path = pathlib.Path(tempfile.mkdtemp())
    with pathlib.Path.open(tmp_path / f"{obj_type.value}.yaml", "w", encoding="utf-8") as f:
        f.write(
            f"""
            - {obj_type.value}:
                name: test-{obj_type.value}
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
    assert zuulcilint_utils.get_zuul_schema(tmp_schema) == {}


def test_get_schema_file_not_found():
    """Test that get_schema() exits when the schema file is not found."""
    tmp_schema = pathlib.Path(tempfile.mkstemp()[1])
    tmp_schema.unlink()
    try:
        zuulcilint_utils.get_zuul_schema(tmp_schema)
    except SystemExit:
        pytest.raises(FileNotFoundError)


def test_get_schema_invalid_json():
    """Test that get_schema() exits when the schema file is invalid."""
    tmp_schema = pathlib.Path(tempfile.mkstemp()[1])
    with pathlib.Path.open(tmp_schema, "w", encoding="utf-8") as f:
        f.write("{- foo = bar}")
        with pytest.raises(SystemExit):
            zuulcilint_utils.get_zuul_schema(tmp_schema)


def test_get_zuul_yaml_files_find():
    """Test that get_zuul_yaml_files() finds files."""
    tmp_path = setup_tmp_list_of_files()
    default_len = 2
    zuul_yaml_files = [f.name for f in zuulcilint_utils.get_zuul_yaml_files(tmp_path)["good_yaml"]]
    assert len(zuul_yaml_files) == default_len
    assert "file0.yaml" in zuul_yaml_files
    assert "file1.yaml" in zuul_yaml_files

    tmp_path = tmp_path / "subdir"
    tmp_path.mkdir()
    assert len(zuulcilint_utils.get_zuul_yaml_files(tmp_path)) == 0

    assert len(zuulcilint_utils.get_zuul_yaml_files(tmp_path / "invalid_path")) == 0


def test_get_zuul_yaml_files_skip():
    """Test that get_zuul_yaml_files() skips files."""
    tmp_path = setup_tmp_list_of_files()
    tmp_path = tmp_path / "subdir"
    tmp_path.mkdir()
    tmp_path = tmp_path / "file2.yaml"
    with pathlib.Path.open(tmp_path, "w", encoding="utf-8") as f:
        f.write("hello")
    assert len(zuulcilint_utils.get_zuul_yaml_files(tmp_path)["good_yaml"]) == 1
    assert len(zuulcilint_utils.get_zuul_yaml_files(tmp_path)["bad_yaml"]) == 0

    tmp_path = tmp_path.parent / "file3.yml"
    with pathlib.Path.open(tmp_path, "w", encoding="utf-8") as f:
        f.write("hello")
    assert len(zuulcilint_utils.get_zuul_yaml_files(tmp_path)["good_yaml"]) == 0
    assert len(zuulcilint_utils.get_zuul_yaml_files(tmp_path)["bad_yaml"]) == 1


def test_get_zuul_object_from_yaml_job():
    """Test that get_zuul_object_from_yaml() returns a list of jobs."""
    tmp_path = setup_zuul_obj_yaml(ZuulObject.JOB)
    jobs = zuulcilint_utils.get_zuul_object_from_yaml(
        ZuulObject.JOB,
        tmp_path / f"{ZuulObject.JOB.value}.yaml",
    )
    jobs_len = 2
    assert len(jobs) == jobs_len
    assert jobs[0]["job"]["name"] == "test-job"


def test_get_zuul_object_from_yaml_nodeset():
    """Test that get_zuul_object_from_yaml() returns a list of nodesets."""
    tmp_path = setup_zuul_obj_yaml(ZuulObject.NODESET)
    nodesets = zuulcilint_utils.get_zuul_object_from_yaml(
        ZuulObject.NODESET,
        tmp_path / f"{ZuulObject.NODESET.value}.yaml",
    )
    assert len(nodesets) == 1
    assert nodesets[0]["nodeset"]["name"] == "test-nodeset"


def test_get_zuul_object_from_yaml_pipeline():
    """Test that get_zuul_object_from_yaml() returns a list of pipelines."""
    tmp_path = setup_zuul_obj_yaml(ZuulObject.PIPELINE)
    pipelines = zuulcilint_utils.get_zuul_object_from_yaml(
        ZuulObject.PIPELINE,
        tmp_path / f"{ZuulObject.PIPELINE.value}.yaml",
    )
    assert len(pipelines) == 1
    assert pipelines[0]["pipeline"]["name"] == "test-pipeline"


def test_get_zuul_object_from_yaml_pragma():
    """Test that get_zuul_object_from_yaml() returns a list of pragmas."""
    tmp_path = setup_zuul_obj_yaml(ZuulObject.PRAGMA)
    pragmas = zuulcilint_utils.get_zuul_object_from_yaml(
        ZuulObject.PRAGMA,
        tmp_path / f"{ZuulObject.PRAGMA.value}.yaml",
    )
    assert len(pragmas) == 1
    assert pragmas[0]["pragma"]["name"] == "test-pragma"


def test_get_zuul_object_from_yaml_project():
    """Test that get_zuul_object_from_yaml() returns a list of projects."""
    tmp_path = setup_zuul_obj_yaml(ZuulObject.PROJECT)
    projects = zuulcilint_utils.get_zuul_object_from_yaml(
        ZuulObject.PROJECT,
        tmp_path / f"{ZuulObject.PROJECT.value}.yaml",
    )
    assert len(projects) == 1
    assert projects[0]["project"]["name"] == "test-project"


def test_get_zuul_object_from_yaml_queue():
    """Test that get_zuul_object_from_yaml() returns a list of queues."""
    tmp_path = setup_zuul_obj_yaml(ZuulObject.QUEUE)
    queues = zuulcilint_utils.get_zuul_object_from_yaml(
        ZuulObject.QUEUE,
        tmp_path / f"{ZuulObject.QUEUE.value}.yaml",
    )
    assert len(queues) == 1
    assert queues[0]["queue"]["name"] == "test-queue"


def test_get_zuul_object_from_yaml_secret():
    """Test that get_zuul_object_from_yaml() returns a list of secrets."""
    tmp_path = setup_zuul_obj_yaml(ZuulObject.SECRET)
    secrets = zuulcilint_utils.get_zuul_object_from_yaml(
        ZuulObject.SECRET,
        tmp_path / f"{ZuulObject.SECRET.value}.yaml",
    )
    assert len(secrets) == 1
    assert secrets[0]["secret"]["name"] == "test-secret"


def test_get_zuul_object_from_yaml_semaphore():
    """Test that get_zuul_object_from_yaml() returns a list of semaphores."""
    tmp_path = setup_zuul_obj_yaml(ZuulObject.SEMAPHORE)
    semaphores = zuulcilint_utils.get_zuul_object_from_yaml(
        ZuulObject.SEMAPHORE,
        tmp_path / f"{ZuulObject.SEMAPHORE.value}.yaml",
    )
    assert len(semaphores) == 1
    assert semaphores[0]["semaphore"]["name"] == "test-semaphore"


def test_get_zuul_object_from_yaml_template():
    """Test that get_zuul_object_from_yaml() returns a list of templates."""
    tmp_path = setup_zuul_obj_yaml(ZuulObject.TEMPLATE)
    templates = zuulcilint_utils.get_zuul_object_from_yaml(
        ZuulObject.TEMPLATE,
        tmp_path / f"{ZuulObject.TEMPLATE.value}.yaml",
    )
    assert len(templates) == 1
    assert templates[0]["project-template"]["name"] == "test-project-template"


def test_get_zuul_object_from_yaml_invalid_yaml():
    """Test exits when the YAML is invalid."""
    tmp_path = setup_zuul_obj_yaml(ZuulObject.JOB)
    with pathlib.Path.open(tmp_path / "job.yaml", "w", encoding="utf-8") as f:
        f.write("{- foo = bar}")
    with pytest.raises(SystemExit):
        zuulcilint_utils.get_zuul_object_from_yaml(ZuulObject.JOB, tmp_path / "job.yaml")


def test_get_zuul_object_from_yaml_no_jobs():
    """Test return an empty list when no jobs are found."""
    tmp_path = setup_zuul_obj_yaml(ZuulObject.JOB)
    with pathlib.Path.open(tmp_path / "no-job.yaml", "w", encoding="utf-8") as f:
        f.write(
            """
            - pipeline:
                name: test-pipeline
            """,
        )
    assert (
        len(zuulcilint_utils.get_zuul_object_from_yaml(ZuulObject.JOB, tmp_path / "no-job.yaml"))
        == 0
    )


def test_get_zuul_object_from_yaml_no_file():
    """Test return an empty list when no file is found."""
    tmp_path = setup_zuul_obj_yaml(ZuulObject.JOB)
    try:
        zuulcilint_utils.get_zuul_object_from_yaml(ZuulObject.JOB, tmp_path / "invalid_file")
    except SystemExit:
        pytest.raises(FileNotFoundError)


def test_get_playbook_paths_from_job():
    """Test that get_playbook_paths_from_job() returns a list of playbook paths."""
    tmp_path = setup_zuul_obj_yaml(ZuulObject.JOB)
    jobs = zuulcilint_utils.get_zuul_object_from_yaml(ZuulObject.JOB, tmp_path / "job.yaml")
    playbook_paths = zuulcilint_utils.get_playbook_paths_from_job(jobs[1].get("job"))
    size = 3
    assert len(playbook_paths) == size
    assert playbook_paths[0] == "playbooks/pre-run.yaml"
    assert playbook_paths[1] == "playbooks/run.yaml"
    assert playbook_paths[2] == "playbooks/post-run.yaml"


def test_get_playbook_paths_from_job_no_playbook_paths():
    """Test return an empty list when no playbook paths are found."""
    tmp_path = setup_zuul_obj_yaml(ZuulObject.JOB)
    with pathlib.Path.open(tmp_path / "job.yaml", "w", encoding="utf-8") as f:
        f.write(
            """
            - job:
                name: test-job
            """,
        )
    jobs = zuulcilint_utils.get_zuul_object_from_yaml(ZuulObject.JOB, tmp_path / "job.yaml")
    playbook_paths = zuulcilint_utils.get_playbook_paths_from_job(jobs[0].get("job"))
    assert len(playbook_paths) == 0


def test_get_files_with_extension():
    """Test return a list of files with the specified extension."""
    tmp_path = setup_tmp_list_of_files()
    files = zuulcilint_utils.get_files_with_extension(tmp_path, "yaml")
    size = 2
    assert len(files) == size
