"""Zuul Linter Tests.

This module contains tests for the Zuul checker module.
"""


import pathlib
import tempfile

import zuullint.checker as zuullint_checker
import zuullint.utils as zuullint_utils


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
    jobs = zuullint_utils.get_jobs_from_zuul_yaml(tmp_path / "job.yaml")

    assert zuullint_checker.check_job_playbook_paths(jobs[0].get("job")) == [
        "playbooks/pre-run.yaml",
        "playbooks/run.yaml",
        "playbooks/post-run.yaml",
    ]
