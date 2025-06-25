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
Type stub file for the function in httpproblem that we use
"""

from http import HTTPStatus
from typing import Optional, TypedDict, overload

class ProblemResponseDict[StatusType: (int, HTTPStatus, None)](TypedDict):
    statusCode: StatusType
    body: str
    headers: dict[str, str]

@overload
def problem_http_response(
    status: None = None,
    title: Optional[str] = None,
    detail: Optional[str] = None,
    type: Optional[str] = None,
    instance: Optional[str] = None,
    headers: Optional[dict[str, str]] = None,
    **kwargs: object,
) -> ProblemResponseDict[None]: ...
@overload
def problem_http_response[StatusType: (
    int,
    HTTPStatus,
)](
    status: StatusType,
    title: Optional[str] = None,
    detail: Optional[str] = None,
    type: Optional[str] = None,
    instance: Optional[str] = None,
    headers: Optional[dict[str, str]] = None,
    **kwargs: object,
) -> ProblemResponseDict[StatusType]: ...
