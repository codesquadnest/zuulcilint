[![Poetry](https://img.shields.io/endpoint?url=https://python-poetry.org/badge/v0.json)](https://python-poetry.org/)
[![Ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json)](https://github.com/astral-sh/ruff)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

# zuulcilint

## Validate from the command line

```
pip install zuulcilint

usage: zuulcilint [-h] [--version] [--check-playbook-paths] [--schema SCHEMA] file [file ...]

positional arguments:
  file                  file(s) or paths to lint

options:
  -h, --help            show this help message and exit
  --version             show program's version number and exit
  --check-playbook-paths, -c
                        check that playbook paths are valid
  --schema SCHEMA, -s SCHEMA
                        path to Zuul schema file
```

## Validate with pre-commit

Add the code below to your `.pre-commit-config.yaml` file:

```yaml
  - repo: https://github.com/codesquadnest/zuulcilint.git
    rev: "1.0"
    hooks:
      - id: zuulcilint
```


## Validate with VS Code

To ease editing Zuul CI configuration file we added experimental support for
a Zuul JSON Schema. This should enable validation and auto-completion in
code editors.

For example on [VSCode](1) you can use the [YAML](2) extension to use such a schema
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

[1]: https://code.visualstudio.com/
[2]: https://marketplace.visualstudio.com/items?itemName=redhat.vscode-yaml
