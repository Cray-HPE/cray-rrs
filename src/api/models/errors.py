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
"""
API Error formatting for the Artifact Repository Service which conforms to
RFC 7807. Also, some frequently used errors encapsulated in functions.
"""
from http import HTTPStatus
from typing import TypedDict
from flask import Response
from httpproblem import problem_http_response


# Used because this type needs to be the same in two places.
# If the status type needs to change, this is the line where it would change.
type statusType = HTTPStatus


class ProblemHttpResponseReturnValue(TypedDict):
    """
    Based on the function definition in https://github.com/cbornet/python-httpproblem/blob/master/httpproblem/problem.py
    And on how we constrain our inputs to it
    """
    statusCode: statusType
    body: str
    headers: dict[str, str]


def problemify(status: statusType, detail: str) -> Response:
    """
    Wrapper for httpproblem.problem_http_response that returns a Flask
    Response object. Conforms to RFC7807 HTTP Problem Details for HTTP APIs.

    Args:
        Subset of httpproblem.problem_http_response. See https://tools.ietf.org/html/rfc7807
        for details on these fields and
        https://github.com/cbornet/python-httpproblem/blob/master/httpproblem/problem.py
        for an explanation.

        problem_http_response kwargs:
            **status
            **title
            **detail
            **type
            **instance
            **kwargs   <-- extension members per RFC 7807

    Returns: flask.Response object of an error in RFC 7807 format
    """
    problem: ProblemHttpResponseReturnValue = problem_http_response(status=status, detail=detail)
    return Response(
        problem["body"], status=problem["statusCode"], headers=problem["headers"]
    )


def generate_missing_input_response() -> Response:
    """
    No input was provided. Reports 400 - Bad Request.

    Returns: results of problemify
    """
    return problemify(
        status=HTTPStatus.BAD_REQUEST,
        detail="No input provided. Determine the specific information that is missing or invalid and "
        "then re-run the request with valid information.",
    )


def generate_resource_not_found_response(detail: str) -> Response:
    """
    Resource with given id was not found. Reports 404 - Not Found.

    Returns: results of problemify
    """
    return problemify(status=HTTPStatus.NOT_FOUND, detail=detail)


def generate_internal_server_error_response(detail: str) -> Response:
    """
    Internal server error occurred. Reports 500 - Internal Server Error.

    Returns: results of problemify
    """
    return problemify(status=HTTPStatus.INTERNAL_SERVER_ERROR, detail=detail)
