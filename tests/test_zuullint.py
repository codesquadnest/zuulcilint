"""Zuul Linter Tests."""
import pathlib
import tempfile

import pytest

import zuullint.utils as zuullint_utils


def test_validate_schema():
    """Test that validate_schema() returns True for valid schema."""
    schema = {"foo": "bar"}
    assert zuullint_utils.validate_schema(schema)