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
Defines all Flask-RESTful resource classes for handling zone and critical service APIs.
"""

from typing import Dict, List, Tuple, Any, Union, cast
from flask import request
from flask_restful import Resource
from src.server.app import app
from src.server.utils.rrs_logging import log_event
from src.server.models.zone_list import ZoneMapper
from src.server.models.zone_describe import ZoneDescriber
from src.server.models.criticalservice_list import CriticalServicesLister
from src.server.models.criticalservice_describe import CriticalServiceDescriber
from src.server.models.criticalservice_update import CriticalServiceUpdater
from src.server.models.criticalservice_status_list import CriticalServiceStatusLister
from src.server.models.criticalservice_status_describe import (
    CriticalServiceStatusDescriber,
)


# Route to get the list of zones
class ZoneListResource(Resource):
    """
    Resource for retrieving the list of all zones.

    This resource handles the GET request to fetch all available zones.
    It returns a list of zones in JSON format.
    """

    def get(self) -> Tuple[Union[List[Dict[str, Any]], Dict[str, str]], int]:
        """
        Get the list of all zones.

        Returns:
            JSON response with the list of zones.
        """
        try:
            log_event("Fetching the list of zones")
            zones = ZoneMapper.get_zones()
            # Use cast to ensure the correct type is returned
            return cast(List[Dict[str, Any]], zones), 200
        except Exception as e:
            log_event(f"Error fetching zones: {str(e)}", level="ERROR")
            return {"error": str(e)}, 500


# Route to describe the zone entered
class ZoneDescribeResource(Resource):
    """
    Resource for describing a specific zone.

    This resource handles the GET request to fetch the description of a
    particular zone, identified by its name.
    """

    def get(self, zone_name: str) -> Tuple[Dict[str, Any], int]:
        """
        Get the description of a specific zone by its name.

        Args:
            zone_name (str): The name of the zone to describe.

        Returns:
            JSON response with the zone description or an error message.
        """
        try:
            log_event(f"Describing zone: {zone_name}")
            zone = ZoneDescriber.describe_zone(zone_name)
            if not zone:
                log_event(f"Zone {zone_name} not found", level="ERROR")
                return {"error": "Zone not found"}, 404
            # Removed redundant cast
            return zone, 200
        except Exception as e:
            log_event(f"Error describing zone {zone_name}: {str(e)}", level="ERROR")
            return {"error": str(e)}, 500


# Route to get the list of critical services
class CriticalServiceListResource(Resource):
    """
    Resource for retrieving the list of all critical services.

    This resource handles the GET request to fetch all available critical services.
    It returns a list of critical services in JSON format.
    """

    def get(self) -> Tuple[Dict[str, Any], int]:
        """
        Get the list of all critical services.

        Returns:
            JSON response with the list of critical services.
        """
        try:
            log_event("Fetching the list of critical services")
            critical_services = CriticalServicesLister.get_critical_service_list()
            return critical_services
        except Exception as e:
            log_event(f"Error fetching critical services: {str(e)}", level="ERROR")
            return {"error": str(e)}, 500


# Route to describe the critical service entered
class CriticalServiceDescribeResource(Resource):
    """
    Resource for describing a specific critical service.

    This resource handles the GET request to fetch the description of a
    particular critical service, identified by its name.
    """

    def get(self, service_name: str) -> Tuple[Dict[str, Any], int]:
        """
        Get the description of a specific critical service status by its name.

        Args:
            service_name (str): The name of the critical service to describe.

        Returns:
            JSON response with the service description or an error message.
        """
        try:
            log_event(f"Describing critical service status: {service_name}")
            result = CriticalServiceDescriber.describe_service(service_name)

            if isinstance(result, tuple) and len(result) == 2:
                return result

            if not result:
                log_event(f"Critical service {service_name} not found", level="ERROR")
                return {"error": "Critical service not found"}, 404

            return result, 200
        except Exception as e:
            log_event(
                f"Error describing service {service_name}: {str(e)}", level="ERROR"
            )
            return {"error": str(e)}, 500


# Route to update the critical services list
class CriticalServiceUpdateResource(Resource):
    """
    Resource for updating the list of critical services.

    This resource handles the PATCH request to update the critical services list.
    """

    def patch(self) -> Tuple[Union[List[Dict[str, Any]], Dict[str, str]], int]:
        """
        Update the list of critical services.

        Returns:
            JSON response with the updated list of critical services.
        """
        try:
            log_event("Updating critical services list")
            new_data = request.get_json()
            if not new_data:
                log_event("No data provided for update", level="ERROR")
                return {"error": "No data provided"}, 400
            updated_services = CriticalServiceUpdater.update_critical_services(new_data)
            return cast(List[Dict[str, Any]], updated_services), 200
        except Exception as e:
            log_event(f"Error updating critical services: {str(e)}", level="ERROR")
            return {"error": str(e)}, 500


# Route to get the list of critical services status
class CriticalServiceStatusListResource(Resource):
    """
    Resource for retrieving the status of all critical services.

    This resource handles the GET request to fetch the status of all critical services.
    It returns a list of critical service statuses in JSON format.
    """

    def get(self) -> Tuple[Dict[str, Any], int]:
        """
        Get the status of all critical services.

        Returns:
            JSON response with the status of critical services.
        """
        try:
            log_event("Fetching critical service statuses")
            status = CriticalServiceStatusLister.get_criticalservice_status_list()
            return status
        except Exception as e:
            log_event(
                f"Error fetching critical service status: {str(e)}", level="ERROR"
            )
            return {"error": str(e)}, 500


# Route to describe the critical service entered
class CriticalServiceStatusDescribeResource(Resource):
    """
    Resource for describing a specific critical service status.

    This resource handles the GET request to fetch the status description of a
    particular critical service, identified by its name.
    """

    def get(self, service_name: str) -> Tuple[Dict[str, Any], int]:
        """
        Get the description of a specific critical service status by its name.

        Args:
            service_name (str): The name of the critical service to describe.

        Returns:
            JSON response with the service description or an error message.
        """
        try:
            log_event(f"Describing critical service status: {service_name}")
            service = CriticalServiceStatusDescriber.describe_service_status(
                service_name
            )
            if not service:
                log_event(f"Critical service {service_name} not found", level="ERROR")
                return {"error": "Critical service not found"}, 404
            return service, 200
        except Exception as e:
            log_event(
                f"Error describing critical service status {service_name}: {str(e)}",
                level="ERROR",
            )
            return {"error": str(e)}, 500