"""Zuul Linter Tests."""
import pathlib
import subprocess
import tempfile

import pytest

from zuullint import __main__ as zuullint


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


def test_invalid():
    """Test that the linter correctly detects errors in an invalid Zuul YAML file.

    Raises
    ------
        pytest.fail: If the linter does not fail as expected.
    """
    try:
        subprocess.check_call(["python", "-m", "zuullint",
                               "tests/data/zuul-config-invalid.yaml"])
    except subprocess.CalledProcessError as e:
        if e.returncode == 1:
            return
        pytest.fail(e)
    pytest.fail("Expected to fail")


def test_valid():
    """Test that the linter does not detect errors in a valid Zuul YAML file.

    Raises
    ------
    pytest.fail: If the linter fails unexpectedly.
    """
    try:
        subprocess.check_call(
            ["python", "-m", "zuullint", "tests/data/zuul-config-valid.yaml"],
        )
    except subprocess.CalledProcessError as e:
        pytest.fail(e)


def test_get_zuul_yaml_files_find():
    """Test that get_zuul_yaml_files() finds files."""
    tmp_path = setup_tmp_list_of_files()
    default_len = 2
    zuul_yaml_files = [file.name for file in zuullint.get_zuul_yaml_files(tmp_path)]
    assert len(zuul_yaml_files) == default_len
    assert "file0.yaml" in zuul_yaml_files
    assert "file1.yaml" in zuul_yaml_files

    tmp_path = tmp_path / "subdir"
    tmp_path.mkdir()
    assert len(zuullint.get_zuul_yaml_files(tmp_path)) == 0

    assert len(zuullint.get_zuul_yaml_files(tmp_path / "invalid_path")) == 0
