"""Configuration file loader for zuulcilint."""

from __future__ import annotations

import json
import pathlib
import sys

import yaml
from jsonschema import Draft201909Validator

_CONFIG_SCHEMA_PATH = pathlib.Path(__file__).parent / "config-schema.json"
_CONFIG_SCHEMA: dict = json.loads(_CONFIG_SCHEMA_PATH.read_text(encoding="utf-8"))

# Flat keys that are valid at the root of a config file (also used to detect
# ambiguous configs that mix a 'zuulcilint:' wrapper with flat-format keys).
_KNOWN_FLAT_KEYS: frozenset[str] = frozenset(
    {"version", "include", "exclude", "warnings-as-errors", "rules", "select", "ignore"}
)

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
    if has_wrapper and flat_keys & _KNOWN_FLAT_KEYS:
        raise ValueError(
            f"{path}: ambiguous config — contains both a 'zuulcilint:' wrapper key "
            f"and flat keys ({flat_keys & _KNOWN_FLAT_KEYS})"
        )
    if has_wrapper:
        raw = raw["zuulcilint"] or {}

    # Validate structure and types against the JSON schema.
    validator = Draft201909Validator(_CONFIG_SCHEMA)
    schema_errors = sorted(validator.iter_errors(raw), key=lambda e: list(e.path))
    if schema_errors:
        messages = "; ".join(e.message for e in schema_errors)
        raise ValueError(f"{path}: invalid config — {messages}")

    # Semantic validation: version value.
    # Rule names and severity values are validated by the JSON schema above.
    if raw.get("version") != 1:
        raise ValueError(
            f"{path}: unsupported version {raw.get('version')!r} — only version 1 is supported"
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


def _resolve_config_path(
    config_path: str | None,
) -> tuple[pathlib.Path | None, str]:
    """Return ``(path, source_description)`` for the highest-priority config.

    Resolution order (highest priority first):
      1. Explicit ``--config`` path.
      2. ``.zuulcilint.yaml`` in the current working directory (repo-level).
      3. ``.zuulcilint.yaml`` in the user's home directory (home-level).

    Returns ``(None, "")`` when no config file is found and no explicit path
    was supplied.
    """
    if config_path is not None:
        path = pathlib.Path(config_path)
        return path, f"explicit (--config {path})"

    repo_config = pathlib.Path.cwd() / ".zuulcilint.yaml"
    if repo_config.is_file():
        return repo_config, "repo (./.zuulcilint.yaml)"

    home_config = pathlib.Path.home() / ".zuulcilint.yaml"
    if home_config.is_file():
        return home_config, "home (~/.zuulcilint.yaml)"

    return None, ""


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
        FileNotFoundError: If an explicit --config path does not exist or is a directory.
        ValueError: If the config file is structurally invalid.
    """
    path, source = _resolve_config_path(config_path)

    if path is None:
        print("[zuulcilint] config: no config file found — using built-in defaults", file=sys.stderr)
        return _default_config()

    print(f"[zuulcilint] config: loading {source} → {path}", file=sys.stderr)
    try:
        merged = _default_config()
        _merge(merged, _load_and_validate(path))
        return merged
    except IsADirectoryError as exc:
        raise FileNotFoundError(f"Config path is a directory, not a file: {path}") from exc
    except FileNotFoundError:
        raise FileNotFoundError(f"Config file not found: {path}") from None
