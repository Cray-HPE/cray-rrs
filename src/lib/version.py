#
# MIT License
#
#  (C) Copyright 2025 Hewlett Packard Enterprise Development LP
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
Rack Resiliency Service Version API
"""

from typing import Tuple, Dict, Any
from http import HTTPStatus
from flask import current_app as app
from flask_restful import Resource
from src.lib.rrs_logging import get_log_id


class Version(Resource):  # type: ignore[misc]
    """Return RRS version information"""

    def get(self) -> Tuple[Dict[str, Any], HTTPStatus]:
        """Return RRS version information"""

        # Generate or fetch a unique log ID for traceability
        log_id = get_log_id()
        app.logger.info("%s ++ version.GET", log_id)

        # Construct the version response from Flask config
        return_value = {
            "version": app.config["VERSION"],
        }

        # Log the constructed response for debugging
        app.logger.debug("%s Returning json response: %s", log_id, return_value)

        # Return version info with HTTP 200 OK
        return return_value, HTTPStatus.OK
