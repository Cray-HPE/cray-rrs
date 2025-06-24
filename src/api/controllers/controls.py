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
This module defines the resources for API Server of the Rack Resiliency Service (RRS).
It provides API endpoints for managing zones and criticalservices, including their
listing, description, updating, and status retrieval.

Classes:
    - ZoneListResource: Handles the retrieval of all zones.
    - ZoneDescribeResource: Handles the description of a specific zone.
    - CriticalServiceListResource: Handles the retrieval of all critical services.
    - CriticalServiceDescribeResource: Handles the description of a specific critical service.
    - CriticalServiceUpdateResource: Handles the updating of critical services.
    - CriticalServiceStatusListResource: Handles the retrieval of the status of all critical services.
    - CriticalServiceStatusDescribeResource: Handles the description of the status of a specific critical service.

Usage:
    These resources are intended to be registered with an API server
    to expose the functionality of Rack Resiliency Service.
"""

import traceback
from typing import Literal, Union
from http import HTTPStatus
from flask import request, Response
from flask_restful import Resource
from src.lib.rrs_logging import log_event
from src.api.services.rrs_zones import ZoneService
from src.lib.schema import (
    ZoneListSchema,
    ZoneDescribeSchema,
    CriticalServicesListSchema,
    CriticalServicesStatusListSchema,
    CriticalServiceStatusDescribeSchema,
    CriticalServiceDescribeSchema,
    CriticalServiceCmStaticType,
    CriticalServiceUpdateSchema,
    ValidateCriticalServiceCmStaticType,
    ValidateServiceName,
    ValidateZoneName,
)
from src.api.services.rrs_criticalservices import (
    CriticalServices,
    CriticalServicesStatus,
)
from src.api.models.errors import (
    generate_bad_request_response,
    generate_internal_server_error_response,
    generate_missing_input_response,
    generate_resource_not_found_response,
)


# Route to get the list of zones
# Ignoring misc subclassing error caused by the lack of type annotations for the flask-restful module
class ZoneListResource(Resource):  # type: ignore[misc,no-any-unimported]
    """
    Resource for retrieving the list of all zones.

    This resource handles the GET request to fetch all available zones.
    It returns a list of zones in JSON format.
    """

    def get(
        self,
    ) -> Union[
        tuple[ZoneListSchema, Literal[HTTPStatus.OK]],
        Response,
    ]:
        """
        Get the list of all zones.

        RRS OAS: #/paths/zones (get)

        Returns:
            JSON response with the list of zones.
        """
        # Log the event of fetching zones
        log_event("Fetching the list of zones")
        try:
            # Retrieve zones using the ZoneMapper utility
            zones = ZoneService.list_zones()
        except Exception as e:
            log_event(traceback.format_exc(), level="ERROR")
            return generate_internal_server_error_response(f"{type(e).__name__}: {e}")
        if "Information" in zones:
            log_event(f"{zones}", level="ERROR")
            return generate_resource_not_found_response(zones["Information"])
        return zones, HTTPStatus.OK


# Route to describe the zone entered
# Ignoring misc subclassing error caused by the lack of type annotations for the flask-restful module
class ZoneDescribeResource(Resource):  # type: ignore[misc,no-any-unimported]
    """
    Resource for describing a specific zone.

    This resource handles the GET request to fetch the description of a
    particular zone, identified by its name.
    """

    def get(
        self, zone_name: str
    ) -> Union[tuple[ZoneDescribeSchema, Literal[HTTPStatus.OK]], Response]:
        """
        Get the description of a specific zone by its name.

        RRS OAS: #/paths/zones/{zone_name} (get)

        Args:
            zone_name (str): The name of the zone to describe.

        Returns:
            JSON response with the zone description or an error message.
        """
        try:
            # Validate the zone_name against the API spec
            ValidateZoneName(zone_name=zone_name)
        except ValueError as e:
            msg = f"Invalid zone name specified: {e}"
            log_event(msg, level="ERROR")
            return generate_bad_request_response(msg)

        # Log the event of describing a specific zone
        log_event(f"Describing zone: {zone_name}")
        try:
            # Fetch the zone description using the ZoneDescriber utility
            zone = ZoneService.describe_zone(zone_name)
        except Exception as e:
            log_event(traceback.format_exc(), level="ERROR")
            return generate_internal_server_error_response(f"{type(e).__name__}: {e}")
        if "Information" in zone:
            log_event(f"{zone}", level="ERROR")
            return generate_resource_not_found_response(zone["Information"])
        if "error" in zone:
            log_event(f"{zone}", level="ERROR")
            return generate_resource_not_found_response(zone["error"])
        return zone, HTTPStatus.OK


# Route to get the list of critical services
# Ignoring misc subclassing error caused by the lack of type annotations for the flask-restful module
class CriticalServiceListResource(Resource):  # type: ignore[misc,no-any-unimported]
    """
    Resource for retrieving the list of all critical services.

    This resource handles the GET request to fetch all available critical services.
    It returns a list of critical services in JSON format.
    """

    def get(
        self,
    ) -> Union[
        tuple[CriticalServicesListSchema, Literal[HTTPStatus.OK]],
        Response,
    ]:
        """
        Get the list of all critical services.

        RRS OAS: #/paths/criticalservices (get)

        Returns:
            JSON response with the list of critical services.
        """
        # Log the event of fetching critical services
        log_event("Fetching the list of critical services")
        try:
            # Retrieve the list of critical services
            critical_services = CriticalServices.get_critical_service_list()
        except Exception as e:
            log_event(traceback.format_exc(), level="ERROR")
            return generate_internal_server_error_response(f"{type(e).__name__}: {e}")
        if "error" in critical_services:
            log_event(f"{critical_services}", level="ERROR")
            return generate_resource_not_found_response(critical_services["error"])
        # Return the list of critical services
        return critical_services, HTTPStatus.OK


# Route to describe the critical service entered
# Ignoring misc subclassing error caused by the lack of type annotations for the flask-restful module
class CriticalServiceDescribeResource(Resource):  # type: ignore[misc,no-any-unimported]
    """
    Resource for describing a specific critical service.

    This resource handles the GET request to fetch the description of a
    particular critical service, identified by its name.
    """

    def get(self, service_name: str) -> Union[
        tuple[CriticalServiceDescribeSchema, Literal[HTTPStatus.OK]],
        Response,
    ]:
        """
        Get the description of a specific critical service status by its name.

        RRS OAS: #/paths/criticalservices/{critical_service_name} (get)

        Args:
            service_name (str): The name of the critical service to describe.

        Returns:
            JSON response with the service description or an error message.
        """
        try:
            # Validate the service_name against the API spec
            ValidateServiceName(service_name=service_name)
        except ValueError as e:
            msg = f"Invalid service name specified: {e}"
            log_event(msg, level="ERROR")
            return generate_bad_request_response(msg)

        # Log the event of describing a specific critical service
        log_event(f"Describing critical service status: {service_name}")
        try:
            # Fetch the critical service description using the CriticalServiceDescriber utility
            result = CriticalServices.describe_service(service_name)
        except Exception as e:
            log_event(traceback.format_exc(), level="ERROR")
            return generate_internal_server_error_response(f"{type(e).__name__}: {e}")
        if "error" in result:
            log_event(f"{result}", level="ERROR")
            return generate_resource_not_found_response(result["error"])
        return result, HTTPStatus.OK


# Route to update the critical services list
# Ignoring misc subclassing error caused by the lack of type annotations for the flask-restful module
class CriticalServiceUpdateResource(Resource):  # type: ignore[misc,no-any-unimported]
    """
    Resource for updating the list of critical services.

    This resource handles the PATCH request to update the critical services list.
    """

    def patch(
        self,
    ) -> Union[
        tuple[CriticalServiceUpdateSchema, Literal[HTTPStatus.OK]],
        Response,
    ]:
        """
        Update the list of critical services.

        RRS OAS: #/paths/criticalservices (patch)

        Returns:
            JSON response with the updated list of critical services.
        """
        # Log the event of updating critical services
        log_event("Updating critical services list")
        try:
            # Get the new data from the request body (assumes JSON)
            new_data: CriticalServiceCmStaticType | None = request.get_json()
        except Exception as e:
            log_event(traceback.format_exc(), level="ERROR")
            return generate_bad_request_response(f"{type(e).__name__}: {e}")

        # If no data is provided, return an error
        if new_data is None:
            log_event("No POST data accompanied in POST Request", level="ERROR")
            return generate_missing_input_response()

        try:
            # Validate the request body against the API spec
            ValidateCriticalServiceCmStaticType(critical_service_cm_static_type=new_data)
        except ValueError as e:
            msg = f"Invalid request body: {e}"
            log_event(msg, level="ERROR")
            return generate_bad_request_response(msg)

        try:
            updated_services = CriticalServices.update_critical_services(new_data)
        except Exception as e:
            log_event(traceback.format_exc(), level="ERROR")
            return generate_internal_server_error_response(f"{type(e).__name__}: {e}")

        if "error" in updated_services:
            log_event(f"{updated_services}", level="ERROR")
            return generate_resource_not_found_response(updated_services["error"])
        return updated_services, HTTPStatus.OK


# Route to get the list of critical services status
# Ignoring misc subclassing error caused by the lack of type annotations for the flask-restful module
class CriticalServiceStatusListResource(Resource):  # type: ignore[misc,no-any-unimported]
    """
    Resource for retrieving the status of all critical services.

    This resource handles the GET request to fetch the status of all critical services.
    It returns a list of critical service statuses in JSON format.
    """

    def get(
        self,
    ) -> Union[
        tuple[CriticalServicesStatusListSchema, Literal[HTTPStatus.OK]],
        Response,
    ]:
        """
        Get the status of all critical services.

        RRS OAS: #/paths/criticalservices/status (get)

        Returns:
            JSON response with the status of critical services.
        """
        # Log the event of fetching critical service statuses
        log_event("Fetching critical service statuses")
        try:
            # Retrieve the status of all critical services
            status = CriticalServicesStatus.get_criticalservice_status_list()
        except Exception as e:
            log_event(traceback.format_exc(), level="ERROR")
            return generate_internal_server_error_response(f"{type(e).__name__}: {e}")
        if "error" in status:
            log_event(f"{status}", level="ERROR")
            return generate_resource_not_found_response(status["error"])
        return status, HTTPStatus.OK


# Route to describe the critical service entered
# Ignoring misc subclassing error caused by the lack of type annotations for the flask-restful module
class CriticalServiceStatusDescribeResource(Resource):  # type: ignore[misc,no-any-unimported]
    """
    Resource for describing a specific critical service status.

    This resource handles the GET request to fetch the status description of a
    particular critical service, identified by its name.
    """

    def get(
        self, service_name: str
    ) -> Union[
        tuple[CriticalServiceStatusDescribeSchema, Literal[HTTPStatus.OK]], Response
    ]:
        """
        Get the description of a specific critical service status by its name.

        RRS OAS: #/paths/criticalservices/status/{critical_service_name} (get)

        Args:
            service_name (str): The name of the critical service to describe.

        Returns:
            JSON response with the service description or an error message.
        """
        try:
            # Validate the service_name against the API spec
            ValidateServiceName(service_name=service_name)
        except ValueError as e:
            msg = f"Invalid service name specified: {e}"
            log_event(msg, level="ERROR")
            return generate_bad_request_response(msg)

        # Log the event of describing a specific critical service status
        log_event(f"Describing critical service status: {service_name}")

        try:
            # Fetch the critical service status using the CriticalServiceStatusDescriber utility
            service = CriticalServicesStatus.describe_service_status(service_name)
        except Exception as e:
            log_event(traceback.format_exc(), level="ERROR")
            return generate_internal_server_error_response(f"{type(e).__name__}: {e}")
        if "error" in service:
            log_event(f"{service}", level="ERROR")
            return generate_resource_not_found_response(service["error"])
        return service, HTTPStatus.OK
