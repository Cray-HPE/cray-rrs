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

import json
from typing import Dict, Literal, Tuple, Union
from http import HTTPStatus
import yaml
from flask import request
from flask_restful import Resource
from kubernetes import client
from src.lib.rrs_logging import log_event
from src.api.services.rrs_zones import ZoneService, ZoneSection
from src.api.models.zones import ErrorDict
from src.api.models.schema import (
    ZoneItemSchema,
    ZoneDescribeSchema,
    CriticalServicesListSchema,
    CriticalServiceDescribeSchema,
    CriticalServicesStatusListSchema,
    CriticalServiceStatusDescribeSchema,
    CriticalServiceUpdateSchema,
)
from src.api.services.rrs_criticalservices import (
    CriticalServices,
    CriticalServicesStatus,
    ListCriticalServiceType,
    DescribeStatusType,
)


# Route to get the list of zones
# Ignoring misc subclassing error caused by the lack of type annotations for the flask-restful module
class ZoneListResource(Resource):  # type: ignore[misc]
    """
    Resource for retrieving the list of all zones.

    This resource handles the GET request to fetch all available zones.
    It returns a list of zones in JSON format.
    """

    def get(
        self,
    ) -> Tuple[
        Union[ZoneItemSchema, ErrorDict],
        Literal[HTTPStatus.INTERNAL_SERVER_ERROR, HTTPStatus.NOT_FOUND, HTTPStatus.OK],
    ]:
        """
        Get the list of all zones.

        Returns:
            JSON response with the list of zones.
        """
        try:
            # Log the event of fetching zones
            log_event("Fetching the list of zones")

            # Retrieve zones using the ZoneMapper utility
            zones = ZoneService.list_zones()
            # If exceptions are caught
            # if "exception" in zones:
            #     log_event(f"{zones}", level="ERROR")
            #     return zones, HTTPStatus.INTERNAL_SERVER_ERROR
            # If the zone does not exist, return a 404 error
            if "Information" in zones:
                log_event(f"{zones}", level="ERROR")
                return zones, HTTPStatus.NOT_FOUND
            return zones, HTTPStatus.OK
        except yaml.YAMLError as e:
            log_event(f" YAML parsing error: {e}", level="ERROR")
            return (
                {"error": f"YAML parsing error: {e}"},
                HTTPStatus.INTERNAL_SERVER_ERROR,
            )
        except TypeError as e:
            log_event(f"Invalid type passed to safe_load: {e}", level="ERROR")
            return (
                {"error": f"Invalid type passed to safe_load: {e}"},
                HTTPStatus.INTERNAL_SERVER_ERROR,
            )
        # except Exception as e:
        #     # Log any error that occurs while fetching zones
        #     log_event(f"Error fetching zones: {str(e)}", level="ERROR")
        #     # Return error message with HTTP 500 status
        #     return {"error": str(e)}, HTTPStatus.INTERNAL_SERVER_ERROR


# Route to describe the zone entered
# Ignoring misc subclassing error caused by the lack of type annotations for the flask-restful module
class ZoneDescribeResource(Resource):  # type: ignore[misc]
    """
    Resource for describing a specific zone.

    This resource handles the GET request to fetch the description of a
    particular zone, identified by its name.
    """

    def get(self, zone_name: str) -> Tuple[
        Union[Dict[str, Union[str, int, ZoneSection]], ErrorDict],
        Literal[HTTPStatus.INTERNAL_SERVER_ERROR, HTTPStatus.NOT_FOUND, HTTPStatus.OK],
    ]:
        """
        Get the description of a specific zone by its name.

        Args:
            zone_name (str): The name of the zone to describe.

        Returns:
            JSON response with the zone description or an error message.
        """
        try:
            # Log the event of describing a specific zone
            log_event(f"Describing zone: {zone_name}")

            # Fetch the zone description using the ZoneDescriber utility
            zone = ZoneService.describe_zone(zone_name)
            # If exceptions are caught
            # if "exception" in zone:
            #     log_event(f"{zone}", level="ERROR")
            #     return zone, HTTPStatus.INTERNAL_SERVER_ERROR
            # If the zone does not exist, return a 404 error
            if "Information" in zone:
                log_event(f"{zone}", level="ERROR")
                return zone, HTTPStatus.NOT_FOUND

            # Return the zone description
            return zone, HTTPStatus.OK
        except yaml.YAMLError as e:
            log_event(f" YAML parsing error: {e}", level="ERROR")
            return (
                {"error": f"YAML parsing error: {e}"},
                HTTPStatus.INTERNAL_SERVER_ERROR,
            )
        except TypeError as e:
            log_event(f"Invalid type passed to safe_load: {e}", level="ERROR")
            return (
                {"error": f"Invalid type passed to safe_load: {e}"},
                HTTPStatus.INTERNAL_SERVER_ERROR,
            )
        # except Exception as e:
        #     # Log any error that occurs while describing the zone
        #     log_event(f"Error describing zone {zone_name}: {str(e)}", level="ERROR")

        #     # Return error message with HTTP 500 status
        #     return {"error": str(e)}, HTTPStatus.INTERNAL_SERVER_ERROR


# Route to get the list of critical services
# Ignoring misc subclassing error caused by the lack of type annotations for the flask-restful module
class CriticalServiceListResource(Resource):  # type: ignore[misc]
    """
    Resource for retrieving the list of all critical services.

    This resource handles the GET request to fetch all available critical services.
    It returns a list of critical services in JSON format.
    """

    def get(
        self,
    ) -> Tuple[
        Union[Dict[str, ListCriticalServiceType], ErrorDict],
        Literal[HTTPStatus.INTERNAL_SERVER_ERROR, HTTPStatus.OK, HTTPStatus.NOT_FOUND],
    ]:
        """
        Get the list of all critical services.

        Returns:
            JSON response with the list of critical services.
        """
        try:
            # Log the event of fetching critical services
            log_event("Fetching the list of critical services")

            # Retrieve the list of critical services
            critical_services = CriticalServices.get_critical_service_list()
            # if "exception" in critical_services:
            #     log_event(f"{critical_services}", level="ERROR")
            #     return critical_services, HTTPStatus.INTERNAL_SERVER_ERROR
            if "error" in critical_services:
                log_event(f"{critical_services}", level="ERROR")
                return critical_services, HTTPStatus.NOT_FOUND
            # Return the list of critical services
            return critical_services, HTTPStatus.OK
        except KeyError as e:
            # log_event(f"Key not found in cm_data.", level="ERROR")
            return {"error": f"{str(e)}"}, HTTPStatus.INTERNAL_SERVER_ERROR
        except TypeError as e:
            # app.logger.error(
            #     "cm_data is not a dict or the value is not a valid string/bytes."
            # )
            return {"error": f"{str(e)}"}, HTTPStatus.INTERNAL_SERVER_ERROR
        except client.exceptions.ApiException as e:
            return {"error": f"{str(e)}"}, HTTPStatus.INTERNAL_SERVER_ERROR
        except json.JSONDecodeError as e:
            # app.logger.error(f"Invalid JSON: {e}")
            return {"error": f"{str(e)}"}, HTTPStatus.INTERNAL_SERVER_ERROR
        except Exception as e:
            # Log any error that occurs while fetching critical services
            log_event(f"Error fetching critical services: {str(e)}", level="ERROR")
            # Return error message with HTTP 500 status
            return {"error": str(e)}, HTTPStatus.INTERNAL_SERVER_ERROR


# Route to describe the critical service entered
# Ignoring misc subclassing error caused by the lack of type annotations for the flask-restful module
class CriticalServiceDescribeResource(Resource):  # type: ignore[misc]
    """
    Resource for describing a specific critical service.

    This resource handles the GET request to fetch the description of a
    particular critical service, identified by its name.
    """

    def get(self, service_name: str) -> Tuple[
        Union[DescribeStatusType, ErrorDict],
        Literal[HTTPStatus.INTERNAL_SERVER_ERROR, HTTPStatus.NOT_FOUND, HTTPStatus.OK],
    ]:
        """
        Get the description of a specific critical service status by its name.

        Args:
            service_name (str): The name of the critical service to describe.

        Returns:
            JSON response with the service description or an error message.
        """
        try:
            # Log the event of describing a specific critical service
            log_event(f"Describing critical service status: {service_name}")

            # Fetch the critical service description using the CriticalServiceDescriber utility
            result = CriticalServices.describe_service(service_name)

            # If the service is not found, return a 404 error
            # if "exception" in result:
            #     log_event(f"{result}", level="ERROR")
            #     return result, HTTPStatus.INTERNAL_SERVER_ERROR
            if "error" in result:
                log_event(f"{result}", level="ERROR")
                return result, HTTPStatus.NOT_FOUND

            # Return the service description
            return result, HTTPStatus.OK
        except KeyError as e:
            # log_event(f"Key not found in cm_data.", level="ERROR")
            return {"error": f"{str(e)}"}, HTTPStatus.INTERNAL_SERVER_ERROR
        except TypeError as e:
            # app.logger.error(
            #     "cm_data is not a dict or the value is not a valid string/bytes."
            # )
            return {"error": f"{str(e)}"}, HTTPStatus.INTERNAL_SERVER_ERROR
        except json.JSONDecodeError as e:
            # app.logger.error(f"Invalid JSON: {e}")
            return {"error": f"{str(e)}"}, HTTPStatus.INTERNAL_SERVER_ERROR
        except client.exceptions.ApiException as e:
            return {"error": f"{str(e)}"}, HTTPStatus.INTERNAL_SERVER_ERROR
        except Exception as e:
            # Log any error that occurs while describing the service
            log_event(
                f"Error describing service {service_name}: {str(e)}", level="ERROR"
            )
            # Return error message with HTTP 500 status
            return {"error": str(e)}, HTTPStatus.INTERNAL_SERVER_ERROR


# Route to update the critical services list
# Ignoring misc subclassing error caused by the lack of type annotations for the flask-restful module
class CriticalServiceUpdateResource(Resource):  # type: ignore[misc]
    """
    Resource for updating the list of critical services.

    This resource handles the PATCH request to update the critical services list.
    """

    def patch(
        self,
    ) -> Tuple[
        Union[Dict[str, object], ErrorDict],
        Literal[
            HTTPStatus.BAD_REQUEST,
            HTTPStatus.INTERNAL_SERVER_ERROR,
            HTTPStatus.OK,
            HTTPStatus.NOT_FOUND,
        ],
    ]:
        """
        Update the list of critical services.

        Returns:
            JSON response with the updated list of critical services.
        """
        try:
            # Log the event of updating critical services
            log_event("Updating critical services list")

            # Get the new data from the request body (assumes JSON)
            new_data = request.get_json()

            # If no data is provided, return an error
            if not new_data:
                log_event("No data provided for update", level="ERROR")
                return {"error": "No data provided"}, HTTPStatus.BAD_REQUEST

            # Update the critical services with the new data
            updated_services = CriticalServices.update_critical_services(new_data)
            if "exception" in updated_services:
                log_event(f"{updated_services}", level="ERROR")
                return updated_services, HTTPStatus.INTERNAL_SERVER_ERROR
            if "error" in updated_services:
                log_event(f"{updated_services}", level="ERROR")
                return updated_services, HTTPStatus.NOT_FOUND
            # Return the updated list of critical services
            return updated_services, HTTPStatus.OK
        except KeyError as e:
            return {"error": f"{str(e)}"}, HTTPStatus.INTERNAL_SERVER_ERROR
        except TypeError as e:
            return {"error": f"{str(e)}"}, HTTPStatus.INTERNAL_SERVER_ERROR
        except json.JSONDecodeError as json_err:
            return {"error": f"{str(json_err)}"}, HTTPStatus.INTERNAL_SERVER_ERROR
        except client.exceptions.ApiException as e:
            return {"error": f"{str(e)}"}, HTTPStatus.INTERNAL_SERVER_ERROR
        except Exception as e:
            # Log any error that occurs while updating the critical services
            log_event(f"Error updating critical services: {str(e)}", level="ERROR")
            # Return error message with HTTP 500 status
            return {"error": str(e)}, HTTPStatus.INTERNAL_SERVER_ERROR


# Route to get the list of critical services status
# Ignoring misc subclassing error caused by the lack of type annotations for the flask-restful module
class CriticalServiceStatusListResource(Resource):  # type: ignore[misc]
    """
    Resource for retrieving the status of all critical services.

    This resource handles the GET request to fetch the status of all critical services.
    It returns a list of critical service statuses in JSON format.
    """

    def get(
        self,
    ) -> Tuple[
        Union[Dict[str, ListCriticalServiceType], ErrorDict],
        Literal[HTTPStatus.INTERNAL_SERVER_ERROR, HTTPStatus.OK, HTTPStatus.NOT_FOUND],
    ]:
        """
        Get the status of all critical services.

        Returns:
            JSON response with the status of critical services.
        """
        try:
            # Log the event of fetching critical service statuses
            log_event("Fetching critical service statuses")

            # Retrieve the status of all critical services
            status = CriticalServicesStatus.get_criticalservice_status_list()
            if "exception" in status:
                log_event(f"{status}", level="ERROR")
                return status, HTTPStatus.INTERNAL_SERVER_ERROR
            if "error" in status:
                log_event(f"{status}", level="ERROR")
                return status, HTTPStatus.NOT_FOUND
            # Return the status of critical services
            return status, HTTPStatus.OK
        except KeyError as e:
            return {"error": f"{str(e)}"}, HTTPStatus.INTERNAL_SERVER_ERROR
        except TypeError as e:
            return {"error": f"{str(e)}"}, HTTPStatus.INTERNAL_SERVER_ERROR
        except json.JSONDecodeError as json_err:
            return {"error": f"{str(json_err)}"}, HTTPStatus.INTERNAL_SERVER_ERROR
        except client.exceptions.ApiException as e:
            return {"error": f"{str(e)}"}, HTTPStatus.INTERNAL_SERVER_ERROR
        except Exception as e:
            # Log any error that occurs while fetching the status
            log_event(
                f"Error fetching critical service status: {str(e)}", level="ERROR"
            )

            # Return error message with HTTP 500 status
            return {"error": str(e)}, HTTPStatus.INTERNAL_SERVER_ERROR


# Route to describe the critical service entered
# Ignoring misc subclassing error caused by the lack of type annotations for the flask-restful module
class CriticalServiceStatusDescribeResource(Resource):  # type: ignore[misc]
    """
    Resource for describing a specific critical service status.

    This resource handles the GET request to fetch the status description of a
    particular critical service, identified by its name.
    """

    def get(self, service_name: str) -> Tuple[
        Union[DescribeStatusType, ErrorDict],
        Literal[HTTPStatus.INTERNAL_SERVER_ERROR, HTTPStatus.NOT_FOUND, HTTPStatus.OK],
    ]:
        """
        Get the description of a specific critical service status by its name.

        Args:
            service_name (str): The name of the critical service to describe.

        Returns:
            JSON response with the service description or an error message.
        """
        try:
            # Log the event of describing a specific critical service status
            log_event(f"Describing critical service status: {service_name}")

            # Fetch the critical service status using the CriticalServiceStatusDescriber utility
            service = CriticalServicesStatus.describe_service_status(service_name)

            # If the service status does not exist, return a 404 error
            if "exception" in service:
                log_event(f"{service}", level="ERROR")
                return service, HTTPStatus.INTERNAL_SERVER_ERROR
            if "error" in service:
                log_event(f"{service}", level="ERROR")
                return service, HTTPStatus.NOT_FOUND

            # Return the service status description
            return service, HTTPStatus.OK
        except yaml.YAMLError as e:
            return (
                {"error": f"YAML parsing error: {e}"},
                HTTPStatus.INTERNAL_SERVER_ERROR,
            )
        except KeyError as e:
            return {"error": f"{str(e)}"}, HTTPStatus.INTERNAL_SERVER_ERROR
        except TypeError as e:
            return {"error": f"{str(e)}"}, HTTPStatus.INTERNAL_SERVER_ERROR
        except json.JSONDecodeError as json_err:
            return {"error": f"{str(json_err)}"}, HTTPStatus.INTERNAL_SERVER_ERROR
        except client.exceptions.ApiException as e:
            return {"error": f"{str(e)}"}, HTTPStatus.INTERNAL_SERVER_ERROR
        except Exception as e:
            # Log any error that occurs while describing the service status
            log_event(
                f"Error describing critical service status {service_name}: {str(e)}",
                level="ERROR",
            )

            # Return error message with HTTP 500 status
            return {"error": str(e)}, HTTPStatus.INTERNAL_SERVER_ERROR
