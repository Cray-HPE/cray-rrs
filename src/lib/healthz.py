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
Kubernetes Health and Liveness functions
"""

from typing import Literal, TypedDict, final
from http import HTTPStatus
from flask import current_app as app
from flask_restful import Resource
from src.lib.rrs_logging import get_log_id


@final
class EmptyDict(TypedDict):
    """
    The API spec dictates an empty dict response for calls to the Healthz endpoints
    A final TypedDict with no keys covers this
    """


EMPTY_DICT = EmptyDict()


# Ignoring misc subclassing error caused by the lack of type annotations for the flask-restful module
class Ready(Resource):  # type: ignore[misc]
    """Return k8s readiness check"""

    def get(self) -> tuple[EmptyDict, Literal[HTTPStatus.OK]]:
        """
        Return k8s readiness check

        OAS: #/paths/healthz/ready (get)
        """
        log_id = get_log_id()  # Get unique log ID for tracing the request
        app.logger.debug("%s ++ healthz/ready.GET", log_id)  # Log readiness check call
        return EMPTY_DICT, HTTPStatus.OK  # Return empty body with HTTP 200 OK


# Ignoring misc subclassing error caused by the lack of type annotations for the flask-restful module
class Live(Resource):  # type: ignore[misc]
    """Return k8s liveness check"""

    def get(self) -> tuple[EmptyDict, Literal[HTTPStatus.OK]]:
        """
        Return k8s liveness check

        OAS: #/paths/healthz/live (get)
        """
        log_id = get_log_id()  # Get unique log ID for tracing the request
        app.logger.debug("%s ++ healthz/live.GET", log_id)  # Log liveness check call
        return EMPTY_DICT, HTTPStatus.OK  # Return empty body with HTTP 200 OK
