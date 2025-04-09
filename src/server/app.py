"""
This Flask application exposes endpoints to interact with zone and critical service data.
It allows retrieving, describing, updating, and checking the status of zones and critical services.
"""

import logging
from typing import Dict, List, Tuple, Any, Union, cast

from flask import Flask, request
from flask_restful import Api, Resource
from src.server.utils.rrs_logging import log_event
from src.server.resources.healthz import Ready, Live
from src.server.models.zone_list import ZoneMapper
from src.server.models.zone_describe import ZoneDescriber
from src.server.models.criticalservice_list import CriticalServicesLister
from src.server.models.criticalservice_describe import CriticalServiceDescriber
from src.server.models.criticalservice_update import CriticalServiceUpdater
from src.server.models.criticalservice_status_list import CriticalServiceStatusLister
from src.server.models.criticalservice_status_describe import (
    CriticalServiceStatusDescriber,
)
from src.server.resources.version import Version

app = Flask(__name__)
api = Api(app)

# Set up logging configuration using Flask's built-in logging system
app.logger.setLevel(logging.INFO)

# Add a handler to log into a file
file_handler = logging.FileHandler("app.log")  # Log to a file named 'app.log'
file_handler.setLevel(logging.INFO)
formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")
file_handler.setFormatter(formatter)

# Add handler to the app's logger
app.logger.addHandler(file_handler)

try:
    with open("/app/.version") as version_file:
        app.config["VERSION"] = version_file.read().splitlines()[0]
except IOError:
    app.config["VERSION"] = "Unknown"

# Endpoint to get the list of zones
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


# Endpoint to describe the zone entered
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


# Endpoint to get the list of critical services
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


# Endpoint to describe the critical service entered
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


# Endpoint to update the critical services list
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


# Endpoint to get the list of critical services status
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


# Endpoint to describe the critical service entered
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


# Add resources to API
api.add_resource(Ready, "/healthz/ready")
api.add_resource(Live, "/healthz/live")
api.add_resource(Version, "/version")
api.add_resource(ZoneListResource, "/zones")
api.add_resource(ZoneDescribeResource, "/zones/<zone_name>")
api.add_resource(CriticalServiceListResource, "/criticalservices")
api.add_resource(CriticalServiceDescribeResource, "/criticalservices/<service_name>")
api.add_resource(CriticalServiceUpdateResource, "/criticalservices")
api.add_resource(CriticalServiceStatusListResource, "/criticalservices/status")
api.add_resource(
    CriticalServiceStatusDescribeResource, "/criticalservices/status/<service_name>"
)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=80, debug=True)
