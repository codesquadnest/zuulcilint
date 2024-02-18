"""Zuul Linter Tests.

This module contains tests for the Zuul checker module.
"""


import pathlib
import tempfile

import zuulcilint.checker as zuulcilint_checker
import zuulcilint.utils as zuulcilint_utils
from zuulcilint.utils import ZuulObject


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


def test_check_job_playbook_paths():
    """Test that check_job_playbook_paths() returns a list of invalid paths."""
    tmp_path = setup_zuul_job_yaml()
    jobs = zuulcilint_utils.get_zuul_object_from_yaml(ZuulObject.JOB, tmp_path / "job.yaml")

    assert zuulcilint_checker.check_job_playbook_paths(jobs[0].get(ZuulObject.JOB.value)) == [
        "playbooks/pre-run.yaml",
        "playbooks/run.yaml",
        "playbooks/post-run.yaml",
    ]


def test_check_duplicated_jobs():
    """Test that duplicated_jobs() returns a set of repeated jobs."""
    jobs = {
        pathlib.Path("job1.yaml"): [
            {"job": {"name": "job1"}},
            {"job": {"name": "job2"}},
            {"job": {"name": "job3"}},
        ],
        pathlib.Path("job2.yaml"): [
            {"job": {"name": "job1"}},
            {"job": {"name": "job2"}},
            {"job": {"name": "job3"}},
        ],
    }

    assert zuulcilint_checker.check_duplicated_jobs(jobs) == {"job1", "job2", "job3"}


def test_check_duplicated_jobs_no_duplicates():
    """Test that duplicated_jobs() returns an empty set when there are no repeated jobs."""
    jobs = {
        pathlib.Path("job1.yaml"): [
            {"job": {"name": "job1"}},
            {"job": {"name": "job2"}},
            {"job": {"name": "job3"}},
        ],
        pathlib.Path("job2.yaml"): [
            {"job": {"name": "job4"}},
            {"job": {"name": "job5"}},
            {"job": {"name": "job6"}},
        ],
    }

    assert not zuulcilint_checker.check_duplicated_jobs(jobs)
