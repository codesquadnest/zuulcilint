"""Configuration file loader for zuulcilint."""

from __future__ import annotations

import pathlib
import sys

import yaml

VALID_RULES = frozenset(
    {
        "check-playbook-paths",
        "check-duplicated-jobs",
        "check-inexistent-nodesets",
        "check-duplicate-semaphore",
    }
)

VALID_SEVERITIES = frozenset({"error", "warning", "disable"})

# Default severities reproduce current CLI-only behaviour exactly.
# check-playbook-paths defaults to "disable" because it is opt-in: it only runs
# when the --check-playbook-paths CLI flag is given, or when a config file
# explicitly sets its severity to "error" or "warning".
DEFAULT_RULES: dict[str, str] = {
    "check-playbook-paths": "disable",
    "check-duplicated-jobs": "warning",
    "check-inexistent-nodesets": "warning",
    "check-duplicate-semaphore": "error",
}


def _default_config() -> dict:
    return {
        "version": 1,
        "include": [],
        "exclude": [],
        "warnings-as-errors": False,
        "rules": DEFAULT_RULES.copy(),
    }


def _resolve_severity(value: str | dict) -> str:
    """Normalise rule severity from either 'error' or {'level': 'error'} form."""
    if isinstance(value, dict):
        value = value.get("level", "")
    return value


def _load_and_validate(path: pathlib.Path) -> dict:
    """Load and validate a single config file, returning the parsed dict."""
    try:
        with pathlib.Path.open(path, encoding="utf-8") as f:
            raw = yaml.safe_load(f)
    except yaml.YAMLError as exc:
        raise ValueError(f"{path}: invalid YAML — {exc}") from exc

    if raw is None:
        raw = {}

    if not isinstance(raw, dict):
        raise ValueError(f"{path}: config root must be a mapping, got {type(raw).__name__}")

    # Support optional top-level 'zuulcilint:' wrapper key.
    # Reject ambiguous files that mix both forms.
    has_wrapper = "zuulcilint" in raw
    flat_keys = set(raw) - {"zuulcilint"}
    known_flat = {"version", "include", "exclude", "warnings-as-errors", "rules", "select", "ignore"}
    if has_wrapper and flat_keys & known_flat:
        raise ValueError(
            f"{path}: ambiguous config — contains both a 'zuulcilint:' wrapper key "
            f"and flat keys ({flat_keys & known_flat})"
        )
    if has_wrapper:
        raw = raw["zuulcilint"] or {}

    if "version" not in raw:
        raise ValueError(f"{path}: missing required 'version' field")
    if raw["version"] != 1:
        raise ValueError(
            f"{path}: unsupported version {raw['version']!r} — only version 1 is supported"
        )

    rules_value = raw.get("rules", {})
    if not isinstance(rules_value, dict):
        raise ValueError(
            f"{path}: 'rules' must be a mapping, got {type(rules_value).__name__}"
        )
    for rule, sev in rules_value.items():
        if rule not in VALID_RULES:
            raise ValueError(f"{path}: unknown rule {rule!r}")
        resolved = _resolve_severity(sev)
        if resolved not in VALID_SEVERITIES:
            raise ValueError(
                f"{path}: invalid severity {sev!r} for rule {rule!r} — "
                f"must be one of {sorted(VALID_SEVERITIES)}"
            )

    return raw


def _merge(base: dict, override: dict) -> None:
    """Merge *override* into *base* in-place.

    Applies the single loaded config file on top of the built-in defaults so
    that partial config files work correctly (unspecified keys keep defaults).
    Rule entries are merged individually; all other keys are replaced outright.
    """
    for key, value in override.items():
        if key == "rules":
            for rule, sev in value.items():
                base["rules"][rule] = _resolve_severity(sev)
        else:
            base[key] = value


def load_config(config_path: str | None = None) -> dict:
    """Resolve zuulcilint configuration using a strict priority order.

    Config sources are mutually exclusive — only the highest-priority source
    found is used.  Resolution order (later/higher overrides earlier/lower):

      1. ~/.zuulcilint.yaml           (user home — lowest priority)
      2. <repo-root>/.zuulcilint.yaml (repo-level)
      3. path passed via --config     (explicit CLI argument — highest priority)

    If no config files are found and no explicit path is given, returns defaults
    that reproduce the current CLI-only behaviour exactly.

    Args:
    ----
        config_path: Optional path supplied via --config CLI argument.

    Returns:
    -------
        Configuration dictionary (merged over built-in defaults).

    Raises:
    ------
        FileNotFoundError: If an explicit --config path does not exist.
        ValueError: If the config file is structurally invalid.
    """
    # --config is highest priority
    if config_path is not None:
        explicit = pathlib.Path(config_path)
        if not explicit.is_file():
            if explicit.is_dir():
                raise FileNotFoundError(f"Config path is a directory, not a file: {explicit}")
            raise FileNotFoundError(f"Config file not found: {explicit}")
        print(f"[zuulcilint] config: loading explicit (--config {explicit}) → {explicit}", file=sys.stderr)
        merged = _default_config()
        _merge(merged, _load_and_validate(explicit))
        return merged

    # Repo-level config takes priority over home-level.
    repo_config = pathlib.Path.cwd() / ".zuulcilint.yaml"
    if repo_config.exists():
        print(f"[zuulcilint] config: loading repo (./.zuulcilint.yaml) → {repo_config}", file=sys.stderr)
        merged = _default_config()
        _merge(merged, _load_and_validate(repo_config))
        return merged

    # Home-level config is the lowest priority fallback.
    home_config = pathlib.Path.home() / ".zuulcilint.yaml"
    if home_config.exists():
        print(f"[zuulcilint] config: loading home (~/.zuulcilint.yaml) → {home_config}", file=sys.stderr)
        merged = _default_config()
        _merge(merged, _load_and_validate(home_config))
        return merged

    print("[zuulcilint] config: no config file found — using built-in defaults", file=sys.stderr)
    return _default_config()
