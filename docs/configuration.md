# zuulcilint Configuration File

zuulcilint supports an optional YAML configuration file for controlling linting behaviour without CLI flags.

## Resolution Order

Config sources are **mutually exclusive** — only the highest-priority source found is used. Resolution order (later/higher overrides earlier/lower):

1. `~/.zuulcilint.yaml` — user home (lowest priority)
2. `<repo-root>/.zuulcilint.yaml` — repository-level config (committed alongside your Zuul files)
3. `--config <path>` — explicit path passed on the CLI (highest priority, overrides both above)

Only one config file is ever loaded. If `--config` is given, home and repo-level files are ignored. If a repo-level file exists, the home-level file is ignored.

## Config Format

Two formats are accepted:

**Flat (recommended):**
```yaml
version: 1
warnings-as-errors: false
include:
  - zuul.d/**
exclude:
  - tests/**
rules:
  check-playbook-paths: error
  check-duplicated-jobs: warning
  check-inexistent-nodesets: warning
  check-duplicate-semaphore: error
```

**Wrapped (`zuulcilint:` key):**
```yaml
zuulcilint:
  version: 1
  rules:
    check-duplicated-jobs: error
```

Mixing both in the same file is rejected with an error.

## Fields

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `version` | integer | — | **Required.** Must be `1`. |
| `warnings-as-errors` | boolean | `false` | Treat all warnings as errors. Equivalent to `--warnings-as-errors`. CLI flag takes precedence. |
| `include` | list of globs | `[]` | Only lint files matching at least one pattern. Matched against repo-relative POSIX paths (e.g. `zuul.d/jobs.yaml`). |
| `exclude` | list of globs | `[]` | Skip files matching any pattern. Applied after `include`. |
| `rules` | mapping | see below | Per-rule severity overrides. |

## Rule Severities

Each rule accepts one of: `error`, `warning`, `disable`.

| Rule | Default | Description |
|------|---------|-------------|
| `check-playbook-paths` | `disable` | Validate that playbook paths referenced in jobs exist on disk. Opt-in: also requires `--check-playbook-paths` CLI flag, or set to `error`/`warning` here to enable without the flag. |
| `check-duplicated-jobs` | `warning` | Detect jobs defined more than once across the scanned files. |
| `check-inexistent-nodesets` | `warning` | Detect jobs referencing nodesets that are not defined. |
| `check-duplicate-semaphore` | `error` | Detect jobs that declare the same semaphore in both `semaphore` and `run`. |

Setting a rule to `disable` skips it entirely — it produces no output and does not affect the exit code.

Promoting a default-`warning` rule to `error` causes a non-zero exit when that rule finds issues.

## CLI Flag Precedence

| Scenario | Behaviour |
|----------|-----------|
| `--warnings-as-errors` CLI flag | Always wins; config `warnings-as-errors: true` is equivalent |
| `--check-playbook-paths` CLI flag | Always runs the check at `error` severity, even if config says `disable` |
| `--config <path>` | Used exclusively; home and repo-level configs are ignored |
| `--ignore-warnings` | Suppresses warning output (unaffected by config) |

## Examples

### Promote all warnings to errors in CI
```yaml
version: 1
warnings-as-errors: true
```

### Lint only files in `zuul.d/`, skip test fixtures
```yaml
version: 1
include:
  - zuul.d/**
exclude:
  - tests/**
```

### Enable playbook path checking via config (no CLI flag needed)
```yaml
version: 1
rules:
  check-playbook-paths: error
```

### Disable a noisy check during migration
```yaml
version: 1
rules:
  check-inexistent-nodesets: disable
```
