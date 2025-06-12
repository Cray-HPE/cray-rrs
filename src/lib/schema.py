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
This module defines various TypedDict schemas for cray-rrs-api
related to zones, nodes, critical services, and pods in CSM Clusters.
These schemas provide a structured way to handle and validate data throughout the cray-rrs-api.
"""
from typing import TypedDict, Literal, final, Required, NotRequired

# Zones Schemas
################################################


@final
class KubernetesTopologyZoneSchema(TypedDict, total=False):
    """
    Schema for Kubernetes topology zone, including master and worker nodes.
    OAS: #/components/schemas/KubernetesTopologyZoneSchema
    """

    Management_Master_Nodes: list[str]
    Management_Worker_Nodes: list[str]


@final
class CephZoneSchema(TypedDict, total=False):
    """
    Schema for Ceph zone, including storage nodes.
    OAS: #/components/schemas/CephZoneSchema
    """

    Management_Storage_Nodes: list[str]


@final
class ZoneItemSchema(TypedDict, total=False):
    """
    Schema for a single zone item, including its name and associated zones.
    OAS: #/components/schemas/ZoneItemSchema
    """

    Zone_Name: Required[str]
    Kubernetes_Topology_Zone: KubernetesTopologyZoneSchema
    CEPH_Zone: CephZoneSchema


@final
class ZoneListSchema(TypedDict):
    """
    Schema for a list of zones.
    OAS: #/components/schemas/ZonesResponse
    """

    Zones: list[ZoneItemSchema]


@final
class NodeSchema(TypedDict):
    """
    Schema for a node, including its name and status.
    OAS: #/components/schemas/NodeSchema
    """

    name: str
    status: str


@final
class StorageNodeSchema(TypedDict):
    """
    Schema for a storage node, including its name, status, and OSDs.
    OAS: #/components/schemas/StorageNodeSchema
    """

    name: str
    status: str
    osds: dict[str, list[str]]


@final
class CephNodeInfo(TypedDict):
    """
    Schema representing a node containing OSDs.
    """

    name: str
    status: str
    osds: list[NodeSchema]


@final
class ManagementMasterSchema(TypedDict, total=False):
    """
    Schema for management master nodes in a Kubernetes topology zone.
    OAS: #/components/schemas/ManagementMasterSchema
    """

    Count: Required[int]
    Type: Required[Literal["Kubernetes_Topology_Zone"]]
    Nodes: list[NodeSchema]


@final
class ManagementWorkerSchema(TypedDict, total=False):
    """
    Schema for management worker nodes in a Kubernetes topology zone.
    OAS: #/components/schemas/ManagementWorkerSchema
    """

    Count: Required[int]
    Type: Required[Literal["Kubernetes_Topology_Zone"]]
    Nodes: list[NodeSchema]


@final
class k8sNodes(TypedDict, total=False):
    """
    Schema for Kubernetes nodes, including masters and workers.
    """

    masters: list[NodeSchema]
    workers: list[NodeSchema]


# Mappings from zone names to k8sNodes
type k8sNodesResultType = dict[str, k8sNodes]
# Mappings from zone names to list[CephNodeInfo]
type cephNodesResultType = dict[str, list[CephNodeInfo]]


@final
class ManagementStorageSchema(TypedDict, total=False):
    """
    Schema for management storage nodes in a Ceph zone.
    OAS: #/components/schemas/ManagementStorageSchema
    """

    Count: Required[int]
    Type: Required[Literal["CEPH_Zone"]]
    Nodes: list[StorageNodeSchema]


@final
class ZoneDescribeSchema(TypedDict, total=False):
    """
    Schema for describing a zone, including its name and management details.
    OAS: #/components/schemas/ZoneDetailResponse
    """

    Zone_Name: Required[str]
    Management_Master: ManagementMasterSchema
    Management_Worker: ManagementWorkerSchema
    Management_Storage: ManagementStorageSchema


# Critical Service Schemas
################################################


@final
class CriticalServiceEntrySchema(TypedDict, total=False):
    """
    Schema for a critical service entry, including its name, type, and status, balanced.
    OAS: #/components/schemas/CriticalServiceEntrySchema
    """

    name: Required[str]
    type: Required[str]
    status: str
    balanced: str


@final
class CriticalServiceCmSchema(TypedDict, total=False):
    """
    Schema for a critical service entry, including its namespace, type, balanced and status.
    """

    type: Required[str]
    namespace: Required[str]
    status: str
    balanced: str


@final
class CriticalServiceCmType(TypedDict):
    """
    Schema for critical services in a configmap, including the service name and its details.
    """

    critical_services: dict[str, CriticalServiceCmSchema]


@final
class CriticalServicesItem(TypedDict, total=False):
    """
    Schema for critical services grouped by namespace.
    OAS: Part of #/components/schemas/CriticalServicesListSchema
    """

    namespace: dict[str, list[CriticalServiceEntrySchema]]


@final
class CriticalServicesListSchema(TypedDict, total=False):
    """
    Schema for a list of critical services.
    OAS: #/components/schemas/CriticalServicesListSchema
    """

    critical_services: CriticalServicesItem


@final
class PodSchema(TypedDict):
    """
    Schema for a pod, including its name, status, node, and zone.
    OAS: #/components/schemas/PodSchema
    """

    Name: str
    Status: str
    Node: str
    Zone: str


@final
class CriticalServiceDescribe(TypedDict, total=False):
    """
    Schema for describing a critical service, including its pods and instances.
    OAS: Part of #/components/schemas/CriticalServiceDescribeSchema and #/components/schemas/CriticalServiceDetail
    """

    Name: Required[str]
    Namespace: Required[str]
    Type: Required[str]
    Status: str
    Balanced: str
    Configured_Instances: Required[int | None]
    Currently_Running_Instances: int
    Pods: list[PodSchema]


@final
class CriticalServiceDescribeSchema(TypedDict, total=False):
    """
    Schema for describing a critical service.
    OAS: #/components/schemas/CriticalServiceDescribeSchema and #/components/schemas/CriticalServiceDetail
    """

    Critical_Service: CriticalServiceDescribe


@final
class CriticalServiceUpdateSchema(TypedDict):
    """
    Schema for updating critical services, including added and existing services.
    OAS: #/components/schemas/CriticalServiceUpdateSchema
    """

    Update: str
    Successfully_Added_Services: list[str]
    Already_Existing_Services: list[str]


# Error Response Schemas
@final
class ErrorDict(TypedDict):
    """
    Schema for error responses.
    OAS: #/components/schemas/ErrorDict
    """

    error: str


@final
class InformationDict(TypedDict):
    """
    Schema for informational responses.
    OAS: #/components/schemas/InformationDict
    """

    Information: str


@final
class extra_properties(TypedDict, total=False):
    """
    This represents ExtraProperties field from the response to a GET request to the
    SLS 'v1/search/hardware' URI.
    https://github.com/Cray-HPE/hms-sls/blob/master/api/openapi.yaml
    #/components/schemas/hardware_extra_properties
    """

    Aliases: list[str]
    Role: str


@final
class slsEntryDataType(TypedDict):
    """
    This represents one of the entries in the response to a GET request to the
    SLS 'v1/search/hardware' URI.
    https://github.com/Cray-HPE/hms-sls/blob/master/api/openapi.yaml
    #/components/schemas/hardware 
    We only use a subset of the fields these entries may have, so we do not define all of the possible fields here.
    This will not cause problems, because we don't ever try to access any fields not defined here.
    """

    Parent: str
    Xname: str
    Type: str
    ExtraProperties: NotRequired[extra_properties]


@final
class component_type(TypedDict):
    """
    This represents one of the entries in a successful response to a GET request to
    the HSM 'v2/State/Components' URI.
    https://github.com/Cray-HPE/hms-smd/blob/master/api/swagger_v2.yaml
    #/definitions/Component.1.0.0_Component
    We only use a subset of the fields these entries may have, so we do not define all of the possible fields here.
    This will not cause problems, because we don't ever try to access any fields not defined here.
    """

    ID: str
    State: str


@final
class hsmDataType(TypedDict):
    """
    This represents a successful response to a GET request to the HSM 'v2/State/Components' URI.
    https://github.com/Cray-HPE/hms-smd/blob/master/api/swagger_v2.yaml
    #/definitions/ComponentArray_ComponentArray
    """

    Components: list[component_type]


@final
class ceph_tree_node_datatype(TypedDict, total=False):
    """
    This represents one of the entries in the nodes list in the output of the "ceph osd tree -f json" command
    We only use a subset of the fields these entries may have, so we do not define all of the possible fields here.
    This will not cause problems, because we don't ever try to access any fields not defined here.
    """

    id: int
    type: str
    name: str
    children: list[int]
    status: str


@final
class cephTreeDataType(TypedDict, total=False):
    """
    This represents the output of the "ceph osd tree -f json" command
    Because we only use the "nodes" field from the output, we do not define any of the other
    fields here, even though there are others. This will not cause problems, because we don't
    ever try to access those fields.
    """

    nodes: list[ceph_tree_node_datatype]


@final
class cephHostDataType(TypedDict, total=False):
    """
    This represents one of the entries in the list in the output of the "ceph orch host ls -f json" command
    We only use a subset of the fields these entries may have, so we do not define all of the possible fields here.
    This will not cause problems, because we don't ever try to access any fields not defined here.
    """

    hostname: str
    status: str


@final
class podInfoType(TypedDict):
    """
    This represents one of the entries in the list that is maintained internally to store pod details.
    """

    Name: str
    Node: str
    Zone: str
    labels: dict[str, str]


@final
class skewReturn(TypedDict, total=False):
    """
    This represents the return type of check_skew function.
    """

    service_name: str
    balanced: str
    status: str
