# Contributing to ZuulCILint

First off, thank you for considering contributing to ZuulCILint! Your contributions help
make this project better for everyone.

## Table of Contents

1. [Code of Conduct](#code-of-conduct)
2. [How Can I Contribute?](#how-can-i-contribute)
    - [Reporting Bugs](#reporting-bugs)
    - [Suggesting Enhancements](#suggesting-enhancements)
    - [Pull Requests](#pull-requests)
3. [Development Setup](#development-setup)
4. [Style Guides](#style-guides)
    - [Commit Messages](#commit-messages)
    - [Python Style Guide](#python-style-guide)
5. [Testing](#testing)

## Code of Conduct

Please read and follow our [Code of Conduct](CODE_OF_CONDUCT.md) to ensure a welcoming
environment for all contributors.

## How Can I Contribute?

### Reporting Bugs

If you find a bug, please report it by opening an issue. Include as much detail as possible
to help us identify and fix the issue quickly. Details might include:

- Steps to reproduce the issue
- Expected and actual results
- Screenshots, if applicable
- Environment details (OS, Python version, etc.)

### Suggesting Enhancements

We welcome suggestions to improve ZuulCILint! To suggest an enhancement:

1. Open an issue with your suggestion.
2. Describe your idea in detail, explaining why it would be beneficial.
3. Include any relevant examples or code snippets.
4. Add the `enhancement` label to the issue.
5. If you're interested in implementing the enhancement, let us know!

### Pull Requests

We love pull requests! If you have a bug fix or an enhancement, please follow these steps:

1. Fork the repository.
2. Create a new branch (`git checkout -b feature/your-feature-name`).
3. Make your changes.
4. Commit your changes (`git commit -am 'Add some feature'`).
5. Push to the branch (`git push origin feature/your-feature-name`).
6. Open a pull request.
7. Include a detailed description of your changes.
8. Link to any related issues or pull requests using keywords (e.g., "Closes #123").
9. Request a review from maintainers.

## Development Setup

To set up a local development environment:

1. Fork and clone the repository.
2. Install [Poetry](https://python-poetry.org/) if you haven't already:
    ```sh
    pip install poetry
    ```
3. Install dependencies and the project in editable mode:
    ```sh
    poetry install
    ```
4. Activate the virtual environment:
    ```sh
    poetry shell
    ```

## Style Guides

### Commit Messages

- Use the present tense ("Add feature" not "Added feature").
- Use the imperative mood ("Move cursor to..." not "Moves cursor to...").
- Limit the first line to 72 characters or less.
- Reference issues and pull requests liberally.

### Python Style Guide

- Follow [PEP 8](https://www.python.org/dev/peps/pep-0008/).
- Use [Black](https://black.readthedocs.io/en/stable/) for code formatting.
- Ensure your code passes linting with [Ruff](https://github.com/charliermarsh/ruff).

## Testing

To run the test suite:

1. Ensure all dependencies are installed:
    ```sh
    poetry install
    ```
2. Run tests with `pytest`:
    ```sh
    poetry run pytest
    ```

## Linting

To run linting checks with `Ruff`:

1. Ensure all dependencies are installed:
    ```sh
    poetry install
    ```
2. Run `Ruff`:
    ```sh
    poetry run ruff check .
    ```

## Using Tox

We use `tox` to automate testing across multiple environments. To run tests with `tox`:

1. Ensure you have `tox` installed:
    ```sh
    poetry install
    ```
2. Run `tox`:
    ```sh
    poetry run tox
    ```

This will run the tests in all specified environments.

---

Thank you for your contributions! Together we can make ZuulCILint better.
