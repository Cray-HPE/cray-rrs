"""Nox definitions for linting, type checks, and tests"""

from __future__ import absolute_import
import nox  # pylint: disable=import-error

PYTHON = ["3"]


@nox.session(python=PYTHON)
def lint(session):
    """Run linters.
    Run Pylint and Pycodestyle against src and tests.
    Returns a failure if the linters find linting errors or sufficiently
    serious code quality issues.
    """
    session.install("-r", "requirements.txt")
    session.install("-r", "requirements-test.txt")
    session.install(".")
    session.log("Running pylint...")
    session.run("pylint", "--rcfile=.pylintrc", "src/*", "tests")

    session.log("Running pycodestyle...")
    session.run("pycodestyle", "--config=.pycodestyle", "src", "tests")


@nox.session(python=PYTHON)
def type_check(session):
    """Run Mypy with config."""
    session.install("-r", "requirements-test.txt")
    session.install(".")
    session.log("Running mypy...")
    session.run("mypy", "--strict")


@nox.session(python=PYTHON)
def tests(session):
    """Default unit test session.
    This is meant to be run against any python version intended to be used.
    """
    # Install all test dependencies, then install this package in-place.
    path = "tests"
    session.install("-r", "requirements-test.txt")
    session.install("-e", ".")

    if session.posargs:
        path = session.posargs[0]

    session.run(
        "pytest",
        "-s",
        "--cov=src",
        "--cov=tests",
        "--cov-append",
        "--cov-config=.coveragerc",
        "--cov-report=",
        path,
        *session.posargs
    )


@nox.session(python=PYTHON)
def cover(session):
    """Run the final coverage report and erase coverage data."""
    session.install("coverage", "pytest-cov")
    session.run("coverage", "report", "--show-missing")
    session.run("coverage", "erase")
