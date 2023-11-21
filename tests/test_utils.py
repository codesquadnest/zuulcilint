"""Zuul Linter Tests."""
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
