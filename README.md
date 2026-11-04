[![Poetry](https://img.shields.io/endpoint?url=https://python-poetry.org/badge/v0.json)](https://python-poetry.org/)
[![Ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json)](https://github.com/astral-sh/ruff)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Known Vulnerabilities](https://snyk.io/test/github/codesquadnest/zuulcilint/badge.svg)](https://snyk.io/advisor/python/zuulcilint)
![CodeRabbit Pull Request Reviews](https://img.shields.io/coderabbit/prs/github/codesquadnest/zuulcilint)

# zuulcilint

zuulcilint is a linter for [Zuul CI](https://zuul-ci.org/) configuration files.
It validates your Zuul YAML (jobs, nodesets, pipelines, projects, secrets,
semaphores, ...) against a JSON Schema and runs a few extra sanity checks, so
mistakes are caught locally or in CI before they reach your Zuul deployment.

Useful Zuul CI references:

- [Zuul documentation](https://zuul-ci.org/docs/zuul/latest/)
- [Project configuration](https://zuul-ci.org/docs/zuul/latest/config/index.html)
- [Job definitions](https://zuul-ci.org/docs/zuul/latest/config/job.html)
- [Nodesets](https://zuul-ci.org/docs/zuul/latest/config/nodeset.html)
- [Semaphores](https://zuul-ci.org/docs/zuul/latest/config/semaphore.html)

## Installation

With pip:

``` bash
pip install zuulcilint
```

With [Poetry](https://python-poetry.org/), from a clone of this repository:

``` bash
poetry install
poetry run zuulcilint --help
```

## Validate from the command line

``` text
usage: zuulcilint [-h] [--version] [--check-playbook-paths] [--schema SCHEMA]
                  [--ignore-warnings] [--warnings-as-errors] [--config PATH]
                  file [file ...]

positional arguments:
  file                  file(s) or paths to lint

options:
  -h, --help            show this help message and exit
  --version             show program's version number and exit
  --check-playbook-paths, -c
                        check that playbook paths are valid
  --schema SCHEMA, -s SCHEMA
                        path to Zuul schema file
  --ignore-warnings, -i
                        ignore warnings
  --warnings-as-errors  handle warnings as errors
  --config PATH         path to a zuulcilint config file (overrides
                        auto-discovered configs)
```

### Usage examples

``` bash
# Lint a single file
zuulcilint .zuul.yaml

# Lint a directory (all Zuul YAML files found are checked)
zuulcilint zuul.d/

# Also verify that playbooks referenced by jobs exist on disk
zuulcilint --check-playbook-paths zuul.d/ playbooks/

# Fail the run on warnings too (useful in CI)
zuulcilint --warnings-as-errors zuul.d/

# Hide warnings
zuulcilint --ignore-warnings zuul.d/

# Use an explicit configuration file
zuulcilint --config .zuulcilint.yaml zuul.d/
```

Using Poetry (from a clone of this repository):

``` bash
poetry install
poetry run zuulcilint .zuul.yaml
poetry run zuulcilint --check-playbook-paths zuul.d/
poetry run zuulcilint --warnings-as-errors zuul.d/
```

The exit code is non-zero when errors are found. See
[docs/configuration.md](docs/configuration.md) for the optional configuration
file (rule severities, include/exclude globs, ...).

### Warnings

By default the following findings are reported as warnings. Use
`--ignore-warnings` to hide them, `--warnings-as-errors` to make them fail the
run, or tune them per rule in the [configuration file](docs/configuration.md).

| Warning | Rule | Rationale |
|---------|------|-----------|
| File extension | n/a | Zuul files should use the `.yaml` extension. A `.yml` file is reported so the repository stays consistent, and so tooling and Zuul's `zuul.d/` conventions that expect `.yaml` pick it up. |
| Duplicate job | `check-duplicated-jobs` | The same job name is defined in more than one scanned file. Zuul merges job variants by name, so an accidental duplicate can silently change job behavior depending on file order. |
| Inexistent nodeset | `check-inexistent-nodesets` | A job references a nodeset (or node) that is not defined in the scanned files. The job would fail at runtime with a configuration error. It may be a false positive if the nodeset is defined in another repository or in the Zuul tenant config. |
| Invalid playbook path | `check-playbook-paths` | A `pre-run`, `run`, `post-run` or `cleanup-run` playbook does not exist on disk. Opt-in via `--check-playbook-paths` or the config file. Paths are resolved relative to the current directory. |

The `check-duplicate-semaphore` rule (a job declaring the same semaphore both
at job level and in a `run` entry) is reported as an **error** by default, since
the semaphore would be acquired twice and can deadlock the job.

## Validate with pre-commit

Add the code below to your `.pre-commit-config.yaml` file:

``` yaml
  - repo: https://github.com/codesquadnest/zuulcilint.git
    rev: "1.0.0"
    hooks:
      - id: zuulcilint
```

## Validate with VS Code

To ease editing Zuul CI configuration file we added experimental support for
a Zuul JSON Schema. This should enable validation and auto-completion in
code editors.

For example on [VSCode](https://code.visualstudio.com) you can use the [YAML](https://marketplace.visualstudio.com/items?itemName=redhat.vscode-yaml) extension to use such a schema
validation by adding the following to `.vscode/settings.json`:

``` json
"yaml.schemas": {
  "https://raw.githubusercontent.com/codesquadnest/zuulcilint/master/zuulcilint/zuul-schema.json": [
      "*zuul-extra.d/***/*.yaml",
      "*zuul.d/**/*.yaml",
      "*zuul.d/**/**/*.yaml",
      "*/.zuul.yaml"
  ]
},
"yaml.customTags": [
  "!encrypted/pkcs1-oaep",
  "!encrypted/pkcs1-oaep sequence",
  "!override",
  "!override sequence",
  "!override mapping",
  "!inherit",
  "!inherit sequence",
  "!inherit mapping"
],
"sortJSON.orderOverride": ["title", "name", "$schema", "version", "description", "type"],
"sortJSON.orderUnderride": ["definitions"]

```
