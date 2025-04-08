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
"""Resource to fetch the Zone details for ceph"""
import yaml
from flask import current_app as app
from src.server.resources.k8s_zones import get_configmap_data
from src.server.resources.rrs_logging import get_log_id


def parse_ceph_zones():
    """Extract Ceph zone details from the ConfigMap."""
    log_id = get_log_id()
    app.logger.info(f"[{log_id}] Fetching Ceph zone details from ConfigMap.")

    configmap_yaml = get_configmap_data()

    if isinstance(configmap_yaml, dict) and "error" in configmap_yaml:
        app.logger.error(
            f"[{log_id}] Error fetching ConfigMap: {configmap_yaml['error']}"
        )
        return configmap_yaml

    if not configmap_yaml:
        app.logger.warning(f"[{log_id}] ConfigMap data is empty or missing.")
        return {"error": "ConfigMap data is empty or missing."}

    try:
        parsed_data = yaml.safe_load(configmap_yaml)
        ceph_zones = parsed_data.get("zone", {}).get("ceph_zones_with_nodes", {})

        zone_mapping = {}

        for zone_name, nodes in ceph_zones.items():
            zone_mapping[zone_name] = []

            for node in nodes:
                node_name = node.get("name")
                node_status = node.get("status", "Unknown")
                osds = node.get("osds", [])

                osd_list = [
                    {"name": osd["name"], "status": osd["status"]} for osd in osds
                ]

                node_info = {"name": node_name, "status": node_status, "osds": osd_list}

                zone_mapping[zone_name].append(node_info)

        if zone_mapping:
            app.logger.info(f"[{log_id}] Successfully parsed Ceph zones.")
        else:
            app.logger.warning(f"[{log_id}] No Ceph zones found.")

        return zone_mapping if zone_mapping else "No Ceph zones present"

    except yaml.YAMLError as e:
        app.logger.error(f"[{log_id}] YAML parsing error: {str(e)}")
        return {"error": f"YAML parsing error: {str(e)}"}
    except Exception as e:
        app.logger.exception(f"[{log_id}] Unexpected error: {str(e)}")
        return {"error": f"Unexpected error: {str(e)}"}
