"""Zuul Linter Tests.

This module contains tests for the Zuul Linter main module.
"""

import subprocess

import pytest


def test_invalid():
    """Test that the linter correctly detects errors in an invalid Zuul YAML file.

    Raises
    ------
        pytest.fail: If the linter does not fail as expected.
    """
    try:
        subprocess.run(
            [
                "python3",
                "-m",
                "zuulcilint",
                "tests/zuul_data_invalid/zuul-config-invalid.yaml",
            ],
            check=True,
            capture_output=True,
        )
    except subprocess.CalledProcessError as e:
        assert "Validation error:" in e.stderr.decode("utf-8")


def test_warnings():
    """Test that the linter detects warnings in a valid Zuul YAML file."""
    result = subprocess.run(
        ["python3", "-m", "zuulcilint", "tests/zuul_data"],
        capture_output=True,
    )

    assert "Found 5 inexistent nodesets" in result.stdout.decode("utf-8")
    assert "Found 1 duplicate jobs" in result.stdout.decode("utf-8")
    assert "Found 1 files with 'yml' extension" in result.stdout.decode("utf-8")


def test_playbook_errors():
    """Test that the linter detects errors in a playbook.

    Raises
    ------
    pytest.fail: If the linter does not detect errors as expected.
    """
    try:
        result = subprocess.run(
            [
                "python3",
                "-m",
                "zuulcilint",
                "--check-playbook-paths",
                "tests/zuul_data",
            ],
            capture_output=True,
        )
        assert result.returncode != 0
        assert "Playbook path errors: 7" in result.stderr.decode("utf-8")
    except subprocess.CalledProcessError as e:
        pytest.fail(f"Subprocess call failed with error: {e}")
