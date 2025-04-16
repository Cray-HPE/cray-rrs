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
"""Resource to fetch the Zone details for Ceph"""

from typing import Dict, List, Union, TypedDict, cast
import yaml
from flask import current_app as app
from src.lib.lib_configmap import ConfigMapHelper
from src.lib.rrs_logging import get_log_id


# TypedDict defining structure of an individual OSD entry
class OsdInfo(TypedDict):
    """Information about a Ceph Object Storage Daemon (OSD)."""

    name: str
    status: str


# TypedDict defining structure of a Ceph node containing OSDs
class NodeInfo(TypedDict):
    """Information about a Ceph storage node including its OSDs."""

    name: str
    status: str
    osds: List[OsdInfo]


# Type aliases for method return values
ZoneMapping = Dict[str, List[NodeInfo]]
ErrorDict = Dict[str, str]
ResultType = Union[ZoneMapping, ErrorDict]


class CephService:
    """Service class to parse Ceph zones from ConfigMap"""

    @staticmethod
    def parse_ceph_zones() -> ResultType:
        """Extract Ceph zone details from the ConfigMap."""
        log_id = get_log_id()
        app.logger.info(f"[{log_id}] Fetching Ceph zone details from ConfigMap.")

        try:
            # Fetch ConfigMap containing Ceph topology
            configmap_yaml = ConfigMapHelper.get_configmap(
                "rack-resiliency", "rrs-mon-dynamic"
            )

            # Return error if ConfigMap fetch fails
            if isinstance(configmap_yaml, dict) and "error" in configmap_yaml:
                app.logger.error(
                    f"[{log_id}] Error fetching ConfigMap: {configmap_yaml['error']}"
                )
                return cast(ErrorDict, configmap_yaml)

            # Handle missing or empty ConfigMap
            if not configmap_yaml:
                app.logger.warning(f"[{log_id}] ConfigMap data is empty or missing.")
                return {"error": "ConfigMap data is empty or missing."}

            # Validate ConfigMap structure
            if not isinstance(configmap_yaml, dict):
                app.logger.error(f"[{log_id}] Invalid ConfigMap format (not a dict)")
                return {"error": "ConfigMap data is not a valid dictionary."}

            try:
                # Parse the YAML content of the ConfigMap
                parsed_data = yaml.safe_load(configmap_yaml["dynamic-data.yaml"])
            except yaml.YAMLError as e:
                app.logger.exception(f"[{log_id}] YAML parsing failed.")
                return {"error": f"Failed to parse ConfigMap YAML: {str(e)}"}

            # Ensure parsed data is a dictionary
            if not isinstance(parsed_data, dict):
                app.logger.error(f"[{log_id}] Invalid format: Expected a dictionary.")
                return {"error": "Invalid format: Expected a dictionary."}

            # Safely extract zone-level data
            zone_data = parsed_data.get("zone", {})
            if not isinstance(zone_data, dict):
                zone_data = {}

            ceph_zones_with_nodes = zone_data.get("ceph_zones_with_nodes", {})
            if not isinstance(ceph_zones_with_nodes, dict):
                ceph_zones_with_nodes = {}

            zone_mapping: ZoneMapping = {}

            # Iterate through each zone and collect node/OSD details
            for zone_name, nodes in ceph_zones_with_nodes.items():
                if not isinstance(nodes, list):
                    continue

                zone_mapping[zone_name] = []

                for node in nodes:
                    if not isinstance(node, dict):
                        continue

                    node_name = node.get("name", "")
                    node_status = node.get("status", "Unknown")
                    osds = node.get("osds", [])
                    if not isinstance(osds, list):
                        osds = []

                    osd_list: List[OsdInfo] = []
                    for osd in osds:
                        if isinstance(osd, dict):
                            osd_list.append(
                                OsdInfo(
                                    name=osd.get("name", ""),
                                    status=osd.get("status", "Unknown"),
                                )
                            )

                    node_info = NodeInfo(
                        name=node_name,
                        status=node_status,
                        osds=osd_list,
                    )

                    zone_mapping[zone_name].append(node_info)

            # Return parsed zone mapping if available
            if zone_mapping:
                app.logger.info(f"[{log_id}] Successfully parsed Ceph zones.")
                return zone_mapping

            # No zones found after parsing
            app.logger.warning(f"[{log_id}] No Ceph zones found.")
            return {"error": "No Ceph zones present"}

        # Catch-all exception handler
        except Exception as e:
            app.logger.exception(
                f"[{log_id}] Unexpected error while parsing Ceph zones."
            )
            return {"error": f"Unexpected error occurred: {str(e)}"}
