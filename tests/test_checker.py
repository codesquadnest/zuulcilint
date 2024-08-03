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


def test_check_duplicated_jobs_empty_jobs():
    """Test that duplicated_jobs() returns an empty set when there are no jobs."""
    jobs = {}

    result = zuulcilint_checker.check_duplicated_jobs(jobs)
    assert len(result) == 0
    assert type(result) is set


def test_check_duplicated_semaphores_no_duplicates():
    """Test that check_duplicate_semaphore() returns an empty list when there are no repeated semaphores."""
    jobs = [
        {"job": {"name": "job1", "semaphore": "semaphore1"}},
    ]

    assert len(zuulcilint_checker.check_duplicate_semaphore(jobs)) == 0


def test_check_duplicated_semaphores_different_job():
    """Test that check_duplicate_semaphore() returns an empty list when there are no repeated semaphores."""
    jobs = [
        {"job": {"name": "job1", "semaphore": "semaphore1"}},
        {"job": {"name": "job2", "semaphore": "semaphore1"}},
        {"job": {"name": "job3", "semaphore": "semaphore2"}},
        {"job": {"name": "job4", "semaphore": "semaphore2"}},
    ]

    assert len(zuulcilint_checker.check_duplicate_semaphore(jobs)) == 0


def test_check_duplicated_semaphores_repeated_semaphores():
    """Test that check_duplicate_semaphore() returns a set of repeated semaphores."""
    jobs = [
        {
            "job": {
                "name": "job1",
                "semaphores": "semaphore1",
                "run": [{"semaphores": "semaphore1"}],
            }
        },
        {
            "job": {
                "name": "job2",
                "semaphores": "semaphore3",
                "run": [{"semaphores": "semaphore2"}],
            }
        },
    ]

    assert zuulcilint_checker.check_duplicate_semaphore(jobs) == {"semaphore1"}


def test_check_duplicated_semaphores_repeated_list_semaphores():
    """Test that check_duplicate_semaphore() returns a set of repeated semaphores
    when semaphores are defined as a list.
    """

    jobs = [
        {
            "job": {
                "name": "job1",
                "semaphores": ["semaphore1", "semaphore2"],
                "run": [{"semaphores": "semaphore1"}],
            }
        },
        {
            "job": {
                "name": "job2",
                "semaphores": ["semaphore3", "semaphore4"],
                "run": [{"semaphores": "semaphore2"}],
            }
        },
    ]

    assert zuulcilint_checker.check_duplicate_semaphore(jobs) == {"semaphore1"}


def test_check_duplicated_semaphores_run_str():
    """Test that check_duplicate_semaphore() returns a set of repeated semaphores
    when semaphores are defined as a list and string.
    """
    jobs = [
        {
            "job": {
                "name": "job1",
                "semaphores": ["semaphore1", "semaphore2"],
                "run": "playbooks/dummy.yaml",
            }
        },
        {
            "job": {
                "name": "job2",
                "semaphores": ["semaphore2", "semaphore4"],
                "run": [
                    {"name": "playbooks/dummy.yaml", "semaphores": "semaphore4"},
                    {"name": "playbooks/dummy2.yaml", "semaphores": "semaphore2"},
                ],
            }
        },
    ]
    assert zuulcilint_checker.check_duplicate_semaphore(jobs) == {"semaphore2", "semaphore4"}


def test_check_duplicated_semaphores_multi_job():
    """Test that check_duplicate_semaphore() returns a set of repeated semaphores
    when semaphores are defined as a string and list.
    """
    jobs = [
        {"job": {"name": "job1", "semaphores": ["semaphore1", "semaphore2"]}},
        {
            "job": {
                "name": "job1",
                "run": [
                    {"name": "playbooks/dummy.yaml", "semaphores": "semaphore1"},
                    {"name": "playbooks/dummy2.yaml", "semaphores": "semaphore2"},
                ],
            }
        },
    ]
    assert zuulcilint_checker.check_duplicate_semaphore(jobs) == {"semaphore1", "semaphore2"}
