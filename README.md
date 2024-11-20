[![Poetry](https://img.shields.io/endpoint?url=https://python-poetry.org/badge/v0.json)](https://python-poetry.org/)
[![Ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json)](https://github.com/astral-sh/ruff)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Known Vulnerabilities](https://snyk.io/test/github/codesquadnest/zuulcilint/badge.svg)](https://snyk.io/advisor/python/zuulcilint)

# zuulcilint

## Validate from the command line

```
pip install zuulcilint

usage: zuulcilint [-h] [--version] [--check-playbook-paths] [--schema SCHEMA] [--ignore-warnings] [--warnings-as-errors] file [file ...]

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
```

## Validate with pre-commit

Add the code below to your `.pre-commit-config.yaml` file:

```yaml
  - repo: https://github.com/codesquadnest/zuulcilint.git
    rev: "0.3.1"
    hooks:
      - id: zuulcilint
```


## Validate with VS Code

To ease editing Zuul CI configuration file we added experimental support for
a Zuul JSON Schema. This should enable validation and auto-completion in
code editors.

For example on [VSCode](https://code.visualstudio.com) you can use the [YAML](https://marketplace.visualstudio.com/items?itemName=redhat.vscode-yaml) extension to use such a schema
validation by adding the following to `.vscode/settings.json`:


```json
"yaml.schemas": {
        "https://raw.githubusercontent.com/codesquadnest/zuulcilint/master/zuulcilint/zuul-schema.json": [
            "*zuul-extra.d/***/*.yaml",
            "*zuul.d/**/*.yaml",
            "*zuul.d/**/**/*.yaml",
            "*/.zuul.yaml"
        ]
},
"yaml.customTags": [
    "!encrypted/pkcs1-oaep array"
],
"sortJSON.orderOverride": ["title", "name", "$schema", "version", "description", "type"],
"sortJSON.orderUnderride": ["definitions"]

```
