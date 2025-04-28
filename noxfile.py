#
# MIT License
#
# (C) Copyright 2025 Hewlett Packard Enterprise Development LP
#
# Permission is hereby granted, free of charge, to any person obtaining a
# copy of this software and associated documentation files (the "Software"),
# to deal in the Software without restriction, including without limitation
# the rights to use, copy, modify, merge, publish, distribute, sublicense,
# and/or sell copies of the Software, and to permit persons to whom the
# Software is furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included
# in all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL
# THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR
# OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE,
# ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR
# OTHER DEALINGS IN THE SOFTWARE.
#
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
