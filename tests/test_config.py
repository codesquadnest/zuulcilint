"""Tests for zuulcilint configuration loading and CLI --config flag."""

from __future__ import annotations

import os
import subprocess
import sys
import textwrap
from collections import Counter

import pytest

from zuulcilint.config import DEFAULT_RULES, VALID_RULES, load_config


# ---------------------------------------------------------------------------
# load_config unit tests
# ---------------------------------------------------------------------------


def test_load_config_no_files_returns_defaults(tmp_path, monkeypatch):
    """With no config files present, defaults are returned."""
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("HOME", str(tmp_path))
    config = load_config()
    assert config["version"] == 1
    assert config["rules"] == DEFAULT_RULES
    assert config["include"] == []
    assert config["exclude"] == []
    assert config["warnings-as-errors"] is False


def test_load_config_explicit_path(tmp_path):
    """Explicit --config path is loaded and merged over defaults."""
    cfg = tmp_path / "my.yaml"
    cfg.write_text(
        textwrap.dedent("""\
            version: 1
            rules:
              check-duplicate-semaphore: warning
        """)
    )
    config = load_config(str(cfg))
    assert config["rules"]["check-duplicate-semaphore"] == "warning"
    # Other rules keep their defaults
    assert config["rules"]["check-duplicated-jobs"] == DEFAULT_RULES["check-duplicated-jobs"]


def test_load_config_missing_explicit_path_raises(tmp_path):
    """FileNotFoundError is raised when the explicit path does not exist."""
    with pytest.raises(FileNotFoundError, match="not found"):
        load_config(str(tmp_path / "nonexistent.yaml"))


def test_load_config_explicit_path_is_directory_raises(tmp_path):
    """FileNotFoundError is raised when --config points to a directory."""
    with pytest.raises(FileNotFoundError, match="directory"):
        load_config(str(tmp_path))


def test_load_config_rules_not_a_mapping_raises(tmp_path):
    """ValueError is raised when 'rules' is not a mapping."""
    cfg = tmp_path / "bad-rules.yaml"
    cfg.write_text("version: 1\nrules: error\n")
    with pytest.raises(ValueError, match="'rules' must be a mapping"):
        load_config(str(cfg))


def test_load_config_flat_format(tmp_path):
    """Flat config format (no 'zuulcilint:' wrapper) is accepted."""
    cfg = tmp_path / ".zuulcilint.yaml"
    cfg.write_text(
        textwrap.dedent("""\
            version: 1
            warnings-as-errors: true
            rules:
              check-inexistent-nodesets: error
        """)
    )
    config = load_config(str(cfg))
    assert config["warnings-as-errors"] is True
    assert config["rules"]["check-inexistent-nodesets"] == "error"


def test_load_config_wrapped_format(tmp_path):
    """Wrapped 'zuulcilint:' format is accepted."""
    cfg = tmp_path / "wrapped.yaml"
    cfg.write_text(
        textwrap.dedent("""\
            zuulcilint:
              version: 1
              rules:
                check-duplicated-jobs: error
        """)
    )
    config = load_config(str(cfg))
    assert config["rules"]["check-duplicated-jobs"] == "error"


def test_load_config_ambiguous_format_raises(tmp_path):
    """A file mixing flat keys and the 'zuulcilint:' wrapper raises ValueError."""
    cfg = tmp_path / "bad.yaml"
    cfg.write_text(
        textwrap.dedent("""\
            version: 1
            zuulcilint:
              rules:
                check-duplicated-jobs: error
        """)
    )
    with pytest.raises(ValueError, match="ambiguous"):
        load_config(str(cfg))


def test_load_config_missing_version_raises(tmp_path):
    """A config file without 'version' raises ValueError."""
    cfg = tmp_path / "no-ver.yaml"
    cfg.write_text("rules:\n  check-duplicated-jobs: error\n")
    with pytest.raises(ValueError, match="missing required 'version'"):
        load_config(str(cfg))


def test_load_config_unsupported_version_raises(tmp_path):
    """A config file with version != 1 raises ValueError."""
    cfg = tmp_path / "v2.yaml"
    cfg.write_text("version: 2\n")
    with pytest.raises(ValueError, match="unsupported version"):
        load_config(str(cfg))


def test_load_config_unknown_rule_raises(tmp_path):
    """A config file with an unknown rule name raises ValueError."""
    cfg = tmp_path / "bad-rule.yaml"
    cfg.write_text("version: 1\nrules:\n  check-made-up-rule: error\n")
    with pytest.raises(ValueError, match="unknown rule"):
        load_config(str(cfg))


def test_load_config_invalid_severity_raises(tmp_path):
    """A config file with an invalid severity raises ValueError."""
    cfg = tmp_path / "bad-sev.yaml"
    cfg.write_text("version: 1\nrules:\n  check-duplicated-jobs: critical\n")
    with pytest.raises(ValueError, match="invalid severity"):
        load_config(str(cfg))


def test_load_config_disable_all_rules(tmp_path):
    """All rules can be set to 'disable'."""
    rules_block = "\n".join(f"  {r}: disable" for r in VALID_RULES)
    cfg = tmp_path / "disable-all.yaml"
    cfg.write_text(f"version: 1\nrules:\n{rules_block}\n")
    config = load_config(str(cfg))
    for rule in VALID_RULES:
        assert config["rules"][rule] == "disable"


def test_load_config_priority_explicit_beats_repo(tmp_path, monkeypatch):
    """Explicit --config is used exclusively; repo-level config is ignored."""
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / ".zuulcilint.yaml").write_text(
        "version: 1\nrules:\n  check-duplicated-jobs: error\n"
    )
    explicit = tmp_path / "explicit.yaml"
    explicit.write_text(
        "version: 1\nrules:\n  check-duplicated-jobs: disable\n"
    )

    monkeypatch.chdir(repo)
    config = load_config(str(explicit))

    # explicit wins exclusively — repo value must NOT bleed through
    assert config["rules"]["check-duplicated-jobs"] == "disable"


def test_load_config_priority_repo_beats_home(tmp_path, monkeypatch):
    """Repo-level config is used exclusively; home-level config is ignored."""
    home = tmp_path / "home"
    home.mkdir()
    repo = tmp_path / "repo"
    repo.mkdir()

    (home / ".zuulcilint.yaml").write_text(
        "version: 1\nrules:\n  check-duplicated-jobs: error\n"
    )
    (repo / ".zuulcilint.yaml").write_text(
        "version: 1\nrules:\n  check-duplicated-jobs: disable\n"
    )

    monkeypatch.setenv("HOME", str(home))
    monkeypatch.chdir(repo)
    config = load_config()

    # repo-level wins — home value must NOT bleed through
    assert config["rules"]["check-duplicated-jobs"] == "disable"


def test_load_config_include_exclude(tmp_path):
    """include/exclude glob lists are returned as-is."""
    cfg = tmp_path / "filters.yaml"
    cfg.write_text(
        textwrap.dedent("""\
            version: 1
            include:
              - zuul.d/**
            exclude:
              - tests/**
        """)
    )
    config = load_config(str(cfg))
    assert config["include"] == ["zuul.d/**"]
    assert config["exclude"] == ["tests/**"]


# ---------------------------------------------------------------------------
# CLI integration tests via subprocess
# ---------------------------------------------------------------------------


def _run(*args, env: dict | None = None) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, "-m", "zuulcilint", *args],
        capture_output=True,
        text=True,
        env=env,
    )


def test_cli_config_invalid_path():
    """--config with a non-existent path exits with an error message."""
    result = _run("--config", "/no/such/file.yaml", "tests/zuul_data")
    assert result.returncode != 0
    assert "Config error" in result.stderr


def test_cli_config_disable_duplicated_jobs(tmp_path):
    """check-duplicated-jobs: disable suppresses the duplicate-jobs warning."""
    cfg = tmp_path / "cfg.yaml"
    cfg.write_text("version: 1\nrules:\n  check-duplicated-jobs: disable\n")
    result = _run("--config", str(cfg), "tests/zuul_data")
    # The duplicate-jobs check is skipped so "duplicate jobs" must not appear
    assert "duplicate jobs" not in result.stdout.lower()


def test_cli_config_promote_duplicated_jobs_to_error(tmp_path):
    """check-duplicated-jobs: error causes a non-zero exit when duplicates exist."""
    cfg = tmp_path / "cfg.yaml"
    cfg.write_text("version: 1\nrules:\n  check-duplicated-jobs: error\n")
    result = _run("--config", str(cfg), "tests/zuul_data")
    assert result.returncode != 0


def test_cli_config_warnings_as_errors_from_config(tmp_path):
    """warnings-as-errors: true in config behaves like --warnings-as-errors flag."""
    cfg = tmp_path / "cfg.yaml"
    cfg.write_text("version: 1\nwarnings-as-errors: true\n")
    result_config = _run("--config", str(cfg), "tests/zuul_data")
    result_flag = _run("--warnings-as-errors", "tests/zuul_data")
    assert result_config.returncode == result_flag.returncode


def test_cli_no_config_preserves_existing_behavior(tmp_path):
    """Running without --config produces the same results as before this feature."""
    isolated_env = {**os.environ, "HOME": str(tmp_path)}
    result = _run("tests/zuul_data", env=isolated_env)
    assert result.returncode == 0
    assert "Found 5 inexistent nodesets" in result.stdout
    assert "Found 1 duplicate jobs" in result.stdout


def test_example_config_is_valid():
    """The bundled example config file loads without errors and matches defaults."""
    from zuulcilint.config import DEFAULT_RULES, load_config

    config = load_config("docs/zuulcilint.example.yaml")
    assert config["version"] == 1
    assert config["rules"] == DEFAULT_RULES
    assert config["warnings-as-errors"] is False
    assert config["include"] == []
    assert config["exclude"] == []


def test_example_config_produces_same_output_as_no_config(tmp_path):
    """Linting with the example config gives identical results to linting without one."""
    isolated_env = {**os.environ, "HOME": str(tmp_path)}
    result_default = _run("tests/zuul_data", env=isolated_env)
    result_example = _run("--config", "docs/zuulcilint.example.yaml", "tests/zuul_data", env=isolated_env)
    assert result_default.returncode == result_example.returncode
    assert Counter(result_default.stdout.splitlines()) == Counter(result_example.stdout.splitlines())


def test_cli_explicit_file_matching_exclude_prints_warning(tmp_path):
    """Explicitly passing a file that matches an exclude pattern prints a warning to stdout."""
    cfg = tmp_path / "cfg.yaml"
    cfg.write_text("version: 1\nexclude:\n  - tests/zuul_data/*.yaml\n")
    # Pass one of the zuul_data files explicitly
    result = _run("--config", str(cfg), "tests/zuul_data/jobs.yaml")
    assert "explicitly passed but matches an exclude pattern" in result.stdout


def test_cli_dir_matching_exclude_no_warning(tmp_path):
    """Passing a directory whose contents are excluded does NOT print a per-file warning."""
    cfg = tmp_path / "cfg.yaml"
    cfg.write_text("version: 1\nexclude:\n  - tests/zuul_data/*.yaml\n")
    result = _run("--config", str(cfg), "tests/zuul_data")
    assert "explicitly passed but matches an exclude pattern" not in result.stdout
