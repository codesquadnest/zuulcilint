"""Tests for zuulcilint configuration loading and CLI --config flag."""

from __future__ import annotations

import textwrap
from collections import Counter

import pytest

from zuulcilint.config import DEFAULT_RULES, VALID_RULES, load_config
from zuulcilint.__main__ import main


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
    with pytest.raises(ValueError, match="is not of type 'object'"):
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
    with pytest.raises(ValueError, match="is a required property"):
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
    with pytest.raises(ValueError, match="Additional properties are not allowed"):
        load_config(str(cfg))


def test_load_config_invalid_severity_raises(tmp_path):
    """A config file with an invalid severity raises ValueError."""
    cfg = tmp_path / "bad-sev.yaml"
    cfg.write_text("version: 1\nrules:\n  check-duplicated-jobs: critical\n")
    with pytest.raises(ValueError, match="is not valid under any"):
        load_config(str(cfg))


def test_load_config_unknown_top_level_key_raises(tmp_path):
    """A config file with an unknown top-level key raises ValueError."""
    cfg = tmp_path / "bad-key.yaml"
    cfg.write_text("version: 1\nunknown-option: true\n")
    with pytest.raises(ValueError, match="invalid config"):
        load_config(str(cfg))


def test_load_config_include_not_a_list_raises(tmp_path):
    """A config file with 'include' as a string (not a list) raises ValueError."""
    cfg = tmp_path / "bad-include.yaml"
    cfg.write_text("version: 1\ninclude: '*.yaml'\n")
    with pytest.raises(ValueError, match="invalid config"):
        load_config(str(cfg))


def test_load_config_exclude_not_a_list_raises(tmp_path):
    """A config file with 'exclude' as a string (not a list) raises ValueError."""
    cfg = tmp_path / "bad-exclude.yaml"
    cfg.write_text("version: 1\nexclude: '*.yaml'\n")
    with pytest.raises(ValueError, match="invalid config"):
        load_config(str(cfg))


def test_load_config_warnings_as_errors_not_bool_raises(tmp_path):
    """A config file with 'warnings-as-errors' as a string raises ValueError."""
    cfg = tmp_path / "bad-wae.yaml"
    cfg.write_text("version: 1\nwarnings-as-errors: 'yes'\n")
    with pytest.raises(ValueError, match="invalid config"):
        load_config(str(cfg))


def test_load_config_version_not_integer_raises(tmp_path):
    """A config file with a string version raises ValueError."""
    cfg = tmp_path / "str-ver.yaml"
    cfg.write_text("version: '1'\n")
    with pytest.raises(ValueError, match="invalid config"):
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
# CLI integration tests via direct main() calls
# ---------------------------------------------------------------------------


def test_cli_config_invalid_path(tmp_path, capsys):
    """--config with a non-existent path exits with an error message."""
    missing = tmp_path / "nonexistent.yaml"
    with pytest.raises(SystemExit) as exc_info:
        main(["--config", str(missing), "tests/zuul_data"])
    assert exc_info.value.code != 0
    assert "Config error" in capsys.readouterr().err


def test_cli_config_disable_duplicated_jobs(tmp_path, capsys):
    """check-duplicated-jobs: disable suppresses the duplicate-jobs warning."""
    cfg = tmp_path / "cfg.yaml"
    cfg.write_text("version: 1\nrules:\n  check-duplicated-jobs: disable\n")
    with pytest.raises(SystemExit):
        main(["--config", str(cfg), "tests/zuul_data"])
    assert "duplicate jobs" not in capsys.readouterr().out.lower()


def test_cli_config_promote_duplicated_jobs_to_error(tmp_path, capsys):
    """check-duplicated-jobs: error causes a non-zero exit when duplicates exist."""
    cfg = tmp_path / "cfg.yaml"
    cfg.write_text("version: 1\nrules:\n  check-duplicated-jobs: error\n")
    with pytest.raises(SystemExit) as exc_info:
        main(["--config", str(cfg), "tests/zuul_data"])
    assert exc_info.value.code != 0


def test_cli_config_warnings_as_errors_from_config(tmp_path, capsys):
    """warnings-as-errors: true in config behaves like --warnings-as-errors flag."""
    cfg = tmp_path / "cfg.yaml"
    cfg.write_text("version: 1\nwarnings-as-errors: true\n")
    with pytest.raises(SystemExit) as exc_config:
        main(["--config", str(cfg), "tests/zuul_data"])
    with pytest.raises(SystemExit) as exc_flag:
        main(["--warnings-as-errors", "tests/zuul_data"])
    assert exc_config.value.code == exc_flag.value.code


def test_cli_no_config_preserves_existing_behavior(tmp_path, monkeypatch, capsys):
    """Running without --config produces the same results as before this feature."""
    monkeypatch.setenv("HOME", str(tmp_path))
    with pytest.raises(SystemExit) as exc_info:
        main(["tests/zuul_data"])
    assert exc_info.value.code == 0
    out = capsys.readouterr().out
    assert "Found 5 inexistent nodesets" in out
    assert "Found 1 duplicate jobs" in out


def test_example_config_is_valid(tmp_path):
    """A default-equivalent config loads without errors and matches defaults."""
    cfg = tmp_path / ".zuulcilint.yaml"
    cfg.write_text(
        textwrap.dedent("""\
            version: 1
            warnings-as-errors: false
            include: []
            exclude: []
            rules:
              check-playbook-paths: disable
              check-duplicated-jobs: warning
              check-inexistent-nodesets: warning
              check-duplicate-semaphore: error
        """)
    )
    config = load_config(str(cfg))
    assert config["version"] == 1
    assert config["rules"] == DEFAULT_RULES
    assert config["warnings-as-errors"] is False
    assert config["include"] == []
    assert config["exclude"] == []


def test_example_config_produces_same_output_as_no_config(tmp_path, monkeypatch, capsys):
    """Linting with a default-equivalent config gives identical results to linting without one."""
    cfg = tmp_path / ".zuulcilint.yaml"
    cfg.write_text(
        textwrap.dedent("""\
            version: 1
            warnings-as-errors: false
            include: []
            exclude: []
            rules:
              check-playbook-paths: disable
              check-duplicated-jobs: warning
              check-inexistent-nodesets: warning
              check-duplicate-semaphore: error
        """)
    )
    monkeypatch.setenv("HOME", str(tmp_path))
    with pytest.raises(SystemExit) as exc_default:
        main(["tests/zuul_data"])
    out_default = capsys.readouterr().out
    with pytest.raises(SystemExit) as exc_example:
        main(["--config", str(cfg), "tests/zuul_data"])
    out_example = capsys.readouterr().out
    assert exc_default.value.code == exc_example.value.code
    assert Counter(out_default.splitlines()) == Counter(out_example.splitlines())


def test_cli_explicit_file_matching_exclude_prints_warning(tmp_path, capsys):
    """Explicitly passing a file that matches an exclude pattern prints a warning to stdout."""
    cfg = tmp_path / "cfg.yaml"
    cfg.write_text("version: 1\nexclude:\n  - tests/zuul_data/*.yaml\n")
    with pytest.raises(SystemExit):
        main(["--config", str(cfg), "tests/zuul_data/jobs.yaml"])
    assert "explicitly passed but matches an exclude pattern" in capsys.readouterr().out


def test_cli_dir_matching_exclude_no_warning(tmp_path, capsys):
    """Passing a directory whose contents are excluded does NOT print a per-file warning."""
    cfg = tmp_path / "cfg.yaml"
    cfg.write_text("version: 1\nexclude:\n  - tests/zuul_data/*.yaml\n")
    with pytest.raises(SystemExit):
        main(["--config", str(cfg), "tests/zuul_data"])
    assert "explicitly passed but matches an exclude pattern" not in capsys.readouterr().out
