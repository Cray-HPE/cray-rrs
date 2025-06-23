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
from enum import StrEnum
from typing import TypedDict, Literal, final, Required, NamedTuple, get_args

# Zones Schemas
################################################


@final
class KubernetesTopologyZoneSchema(TypedDict, total=False):
    """
    Schema for Kubernetes topology zone, including master and worker nodes.
    RRS OAS: #/components/schemas/KubernetesTopologyZoneSchema
    """

    Management_Master_Nodes: list[str]
    Management_Worker_Nodes: list[str]


@final
class CephZoneSchema(TypedDict):
    """
    Schema for Ceph zone, including storage nodes.
    RRS OAS: #/components/schemas/CephZoneSchema
    """

    Management_Storage_Nodes: list[str]


@final
class ZoneItemSchema(TypedDict, total=False):
    """
    Schema for a single zone item, including its name and associated zones.
    RRS OAS: #/components/schemas/ZoneItemSchema
    """

    Zone_Name: Required[str]
    Kubernetes_Topology_Zone: KubernetesTopologyZoneSchema
    CEPH_Zone: CephZoneSchema


@final
class ZoneListSchema(TypedDict):
    """
    Schema for a list of zones.
    RRS OAS: #/components/schemas/ZonesResponse
    """

    Zones: list[ZoneItemSchema]


@final
class NodeSchema(TypedDict):
    """
    Schema for a node, including its name and status.
    RRS OAS: #/components/schemas/NodeSchema
    """

    name: str
    status: Literal["Ready", "NotReady", "Unknown"]


StatusReady = Literal["Ready", "NotReady"]


@final
class OSDSchema(TypedDict):
    """
    Schema for an OSD, including its name and status.
    """

    name: str
    status: Literal["up", "down"]


@final
class OSDStatesSchema(TypedDict, total=False):
    """
    Schema for OSD states with up and down fields.
    RRS OAS: #/components/schemas/OSDStatesSchema
    """

    up: list[str]
    down: list[str]


@final
class StorageNodeSchema(TypedDict):
    """
    Schema for a storage node, including its name, status, and OSDs.
    RRS OAS: #/components/schemas/StorageNodeSchema
    """

    name: str
    status: StatusReady
    osds: OSDStatesSchema


@final
class CephNodeInfo(TypedDict):
    """
    Schema representing a node containing OSDs.
    """

    name: str
    status: StatusReady
    osds: list[OSDSchema]


@final
class ManagementKubernetesSchema(TypedDict):
    """
    Schema for management master or worker nodes in a Kubernetes topology zone.
    RRS OAS: #/components/schemas/ManagementKubernetesSchema
    """

    Count: int
    Type: Literal["Kubernetes_Topology_Zone"]
    Nodes: list[NodeSchema]


@final
class k8sNodes(TypedDict, total=False):
    """
    Schema for Kubernetes nodes, including masters and workers.
    """

    masters: list[NodeSchema]
    workers: list[NodeSchema]


k8sNodeTypes = Literal["masters", "workers"]
k8sNodeTypeTuple: tuple[k8sNodeTypes, k8sNodeTypes] = ("masters", "workers")


# Mappings from zone names to k8sNodes
type k8sNodesResultType = dict[str, k8sNodes]
# Mappings from zone names to list[CephNodeInfo]
type cephNodesResultType = dict[str, list[CephNodeInfo]]


@final
class ManagementStorageSchema(TypedDict):
    """
    Schema for management storage nodes in a Ceph zone.
    RRS OAS: #/components/schemas/ManagementStorageSchema
    """

    Count: int
    Type: Literal["CEPH_Zone"]
    Nodes: list[StorageNodeSchema]


@final
class ZoneDescribeSchema(TypedDict, total=False):
    """
    Schema for describing a zone, including its name and management details.
    RRS OAS: #/components/schemas/ZoneDetailResponse
    """

    Zone_Name: Required[str]
    Management_Master: ManagementKubernetesSchema
    Management_Worker: ManagementKubernetesSchema
    Management_Storage: ManagementStorageSchema


# Critical Service Schemas
################################################

# RRS OAS: #/components/schemas/ServiceBalanced
ServiceBalanced = Literal["true", "false", "NA"]
# RRS OAS: #/components/schemas/ServiceStatus
ServiceStatus = Literal[
    "error",
    "Configured",
    "PartiallyConfigured",
    "NotConfigured",
    "Running",
    "Unconfigured",
]
# RRS OAS: #/components/schemas/ServiceType
ServiceType = Literal["Deployment", "StatefulSet"]


@final
class CriticalServiceStatusItemSchema(TypedDict):
    """
    Schema for a critical service entry, including its name, type, and status, balanced.
    RRS OAS: #/components/schemas/CriticalServiceStatusItemSchema
    """

    name: str
    type: ServiceType
    status: ServiceStatus
    balanced: ServiceBalanced


@final
class CriticalServiceItemSchema(TypedDict):
    """
    Schema for a critical service entry, including its name and type.
    RRS OAS: #/components/schemas/CriticalServiceItemSchema
    """

    name: str
    type: ServiceType


@final
class CriticalServiceCmStaticSchema(TypedDict):
    """
    Schema for a critical service configuration in static ConfigMap.
    RRS OAS: #/components/schemas/CriticalServiceCmStaticSchema
    """

    namespace: str
    type: ServiceType


@final
class CriticalServiceCmStaticType(TypedDict):
    """
    Schema for critical services in static ConfigMap.
    RRS OAS: #/components/schemas/CriticalServiceCmStaticType
    """

    critical_services: dict[str, CriticalServiceCmStaticSchema]


@final
class CriticalServiceCmDynamicSchema(TypedDict):
    """
    Schema for a critical service entry, including its namespace, type, balanced and status.
    """

    namespace: str
    type: ServiceType
    status: ServiceStatus
    balanced: ServiceBalanced


@final
class CriticalServiceCmDynamicType(TypedDict):
    """
    Schema for critical services in a configmap, including the service name and its details.
    """

    critical_services: dict[str, CriticalServiceCmDynamicSchema]


@final
class CriticalServiceCmMixedType(TypedDict):
    """
    Schema for critical services in a configmap, including the service name and its details.
    """

    critical_services: dict[
        str, CriticalServiceCmDynamicSchema | CriticalServiceCmStaticSchema
    ]


@final
class CriticalServicesItem(TypedDict):
    """
    Schema for critical services grouped by namespace.
    OAS: Part of #/components/schemas/CriticalServicesListSchema
    """

    namespace: dict[str, list[CriticalServiceItemSchema]]


@final
class CriticalServicesStatusItem(TypedDict):
    """
    Schema for critical services grouped by namespace.
    OAS: Part of #/components/schemas/CriticalServicesStatusListSchema
    """

    namespace: dict[str, list[CriticalServiceStatusItemSchema]]


@final
class CriticalServicesListSchema(TypedDict):
    """
    Schema for a list of critical services.
    RRS OAS: #/components/schemas/CriticalServicesListSchema
    """

    critical_services: CriticalServicesItem


@final
class CriticalServicesStatusListSchema(TypedDict):
    """
    Schema for a list of critical services.
    RRS OAS: #/components/schemas/CriticalServicesStatusListSchema
    """

    critical_services: CriticalServicesStatusItem


@final
class PodSchema(TypedDict):
    """
    Schema for a pod, including its name, status, node, and zone.
    RRS OAS: #/components/schemas/PodSchema
    """

    name: str
    status: Literal["Running", "Pending", "Failed", "Terminating"]
    node: str
    zone: str


@final
class CriticalServiceDescribe(TypedDict):
    """
    Schema for describing a critical service, including its pods and instances.
    OAS: Part of #/components/schemas/CriticalServiceDescribeSchema
    """

    name: str
    namespace: str
    type: ServiceType
    configured_instances: int | None


@final
class CriticalServiceStatusDescribe(TypedDict):
    """
    Schema for describing a critical service, including its pods and instances.
    OAS: Part of #/components/schemas/CriticalServiceStatusDescribeSchema
    """

    name: str
    namespace: str
    type: ServiceType
    status: ServiceStatus
    balanced: ServiceBalanced
    configured_instances: int | None
    currently_running_instances: int | None
    pods: list[PodSchema]


@final
class CriticalServiceDescribeSchema(TypedDict):
    """
    Schema for describing a critical service.
    RRS OAS: #/components/schemas/CriticalServiceDescribeSchema
    """

    critical_service: CriticalServiceDescribe


@final
class CriticalServiceStatusDescribeSchema(TypedDict):
    """
    Schema for describing a critical service.
    RRS OAS: #/components/schemas/CriticalServiceStatusDescribeSchema
    """

    critical_service: CriticalServiceStatusDescribe


@final
class CriticalServiceUpdateSchema(TypedDict):
    """
    Schema for response to updating critical services, including added and existing services.
    RRS OAS: #/components/schemas/CriticalServiceUpdateSchema
    """

    Update: str
    Successfully_Added_Services: list[str]
    Already_Existing_Services: list[str]


# RMS schemas


RMS_STATES = Literal[
    "Ready",
    "Started",
    "Waiting",
    "Monitoring",
    "Fail_notified",
    "internal_failure",
    "init",
    "init_fail",
]


class RMSState(StrEnum):
    """Enum representing the states of the Rack Resiliency Service (RRS)."""

    READY = "Ready"
    STARTED = "Started"
    WAITING = "Waiting"
    MONITORING = "Monitoring"
    FAIL_NOTIFIED = "Fail_notified"
    INTERNAL_FAILURE = "internal_failure"
    INIT = "init"
    INIT_FAIL = "init_fail"


# Error Response Schemas
@final
class ErrorDict(TypedDict):
    """
    Schema for error responses.
    RRS OAS: #/components/schemas/ErrorDict
    """

    error: str


@final
class InformationDict(TypedDict):
    """
    Schema for informational responses.
    """

    Information: str


# External API schemas


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
class slsEntryDataType(TypedDict, total=False):
    """
    This represents one of the entries in the response to a GET request to the
    SLS 'v1/search/hardware' URI.
    https://github.com/Cray-HPE/hms-sls/blob/master/api/openapi.yaml
    #/components/schemas/hardware
    We only use a subset of the fields these entries may have, so we do not define all of the possible fields here.
    This will not cause problems, because we don't ever try to access any fields not defined here.
    """

    Parent: str
    Xname: Required[str]
    Type: str
    ExtraProperties: extra_properties


@final
class component_type(TypedDict, total=False):
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
class hsmDataType(TypedDict, total=False):
    """
    This represents a successful response to a GET request to the HSM 'v2/State/Components' URI.
    https://github.com/Cray-HPE/hms-smd/blob/master/api/swagger_v2.yaml
    #/definitions/ComponentArray_ComponentArray
    """

    Components: list[component_type]


@final
class hmnfdSubscribePost(TypedDict, total=False):
    """
    This represents one item in a successful response to a GET request to the HMNFD '/subscriptions' URI.
    https://github.com/Cray-HPE/hms-hmnfd/blob/master/api/swagger_v2.yaml
    #/components/schemas/SubscribePost
    We only use a subset of the fields these entries may have, so we do not define all of the possible fields here.
    This will not cause problems, because we don't ever try to access any fields not defined here.
    """

    Subscriber: str
    SubscriberAgent: str


@final
class hmnfdSubscriptionListArray(TypedDict, total=False):
    """
    This represents a successful response to a GET request to the HMNFD '/subscriptions' URI.
    https://github.com/Cray-HPE/hms-hmnfd/blob/master/api/swagger_v2.yaml
    #/components/schemas/SubscriptionListArray
    """

    SubscriptionList: list[hmnfdSubscribePost]


# Despite what the HMNFD schema claims, these enumerated types are actually not case sensitive.
# When listing subscriptions from HMNFD with a GET, all of these values are all lowercase.
# When receiving a change POST notification from HMNFD, these values have their first letter capitalized.
# And when accepting values as input, it accepts either way (and possibly may be completely case insensitive).
# This is not reflected in the official schema.
# https://github.com/Cray-HPE/hms-hmnfd/blob/master/api/swagger_v2.yaml

# #/components/schemas/HMSState.1.0.0
hmnfdState = Literal[
    "unknown",
    "empty",
    "populated",
    "off",
    "on",
    "active",
    "standby",
    "halt",
    "ready",
    "paused",
]
# This allows us to have an object listing all of the supported states available at runtime
HMNFD_STATES: frozenset[hmnfdState] = frozenset(get_args(hmnfdState))
hmnfdNotificationState = Literal[
    "Unknown",
    "Empty",
    "Populated",
    "Off",
    "On",
    "Active",
    "Standby",
    "Halt",
    "Ready",
    "Paused",
]


@final
class hmnfdSubscribePostV2(TypedDict, total=False):
    """
    This represents the request body for a POST request to the HMNFD
    '/subscriptions/{subscriber_node}/agents/{agent_name}' URI.
    https://github.com/Cray-HPE/hms-hmnfd/blob/master/api/swagger_v2.yaml
    #/components/schemas/SubscribePostV2
    We only use a subset of the fields these entries may have, so we do not define all of the possible fields here.
    """

    Components: list[str]
    States: list[hmnfdState]
    Url: str
    Enabled: bool


@final
class hmnfdNotificationPost(TypedDict, total=False):
    """
    This represents the request body for a POST request made from HMNFD to RMS, notifying
    of a state or role change.
    OAS: #/components/responses/SCNRequestSchema

    https://github.com/Cray-HPE/hms-hmnfd/blob/master/api/swagger_v2.yaml
    #/components/schemas/StateChanges

    We only use a subset of the fields these entries may have, so we do not define all of the possible fields here.
    I also note that the actual object appears to always contain a Timestamp field, which is not documented
    in the HMNFD spec. We do not use it, so I also omit it here.

    RMS subscribes to notifications for changes in State or Role. So one of these objects is guaranteed to have
    one of those fields, but is not required to have either one specifically. There is no way to capture that in a
    single TypeDict definition, so for simplicity we will mark both as not required.
    """

    Components: Required[list[str]]
    State: hmnfdNotificationState


@final
class openidTokenResponse(TypedDict, total=False):
    """
    This represents a successful response to a POST request to:
    https://api-gw-service-nmn.local/keycloak/realms/shasta/protocol/openid-connect/token
    We do not define all of the possible fields here.
    This will not cause problems, because we don't ever try to access any fields not defined here.
    """

    access_token: str


@final
class cephOrchPsService(TypedDict):
    """
    This represents one entry in the list output of `ceph orch ps -f json`
    Not all fields are specified -- only the ones we care about
    """

    hostname: str
    service_name: str
    status_desc: str


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
    status: Literal["up", "down"]


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
    status: Literal["", "online", "offline"]


@final
class cephStatusHealthChecksPgDegradedSummary(TypedDict, total=False):
    """
    This represents the "health"."checks"."PG_DEGRADED"."summary" field in the output of `ceph -s -f json`
    """

    message: str


@final
class cephStatusHealthChecksPgDegraded(TypedDict, total=False):
    """
    This represents the "health"."checks"."PG_DEGRADED" field in the output of `ceph -s -f json`
    """

    summary: cephStatusHealthChecksPgDegradedSummary


@final
class cephStatusHealthChecks(TypedDict, total=False):
    """
    This represents the "health"."checks" field in the output of `ceph -s -f json`
    """

    PG_DEGRADED: cephStatusHealthChecksPgDegraded


@final
class cephStatusHealth(TypedDict, total=False):
    """
    This represents the "health" field in the output of `ceph -s -f json`
    """

    checks: cephStatusHealthChecks
    status: str


@final
class cephStatus(TypedDict, total=False):
    """
    This represents partial output of the `ceph -s -f json` command
    """

    health: cephStatusHealth
    pgmap: dict[str, object]


@final
class podInfoType(TypedDict):
    """
    This represents one of the entries in the list that is maintained internally to store pod details.
    """

    Name: str
    Node: str
    Zone: str
    labels: dict[str, str]


class skewReturn(NamedTuple):
    """
    This represents the return type of check_skew function.
    """

    service_name: str
    balanced: ServiceBalanced
    error: bool = False


@final
class EmptyDict(TypedDict):
    """
    The API spec dictates an empty dict response for calls to the Healthz endpoints
    A final TypedDict with no keys covers this
    RMS/RRS OAS: #/components/schemas/EmptyDict
    """


@final
class VersionInfo(TypedDict):
    """
    RMS/RRS OAS: #/components/schemas/VersionSchema
    """

    version: str


################################################
# The schemas for dynamic-data from dynamic configmap
@final
class CrayRRSPod(TypedDict):
    """
    Schema for capturing Cray RRS Pod location details.
    """

    node: str
    rack: str | None
    zone: str | None


# Timestamps Schema
@final
class TimestampsSchema(TypedDict, total=False):
    """
    Schema for tracking system-wide monitoring and service timestamps.
    """

    end_timestamp_ceph_monitoring: str
    end_timestamp_k8s_monitoring: str
    init_timestamp: str
    last_update_timestamp: str
    start_timestamp_api: str
    start_timestamp_ceph_monitoring: str
    start_timestamp_k8s_monitoring: str
    start_timestamp_rms: str


# State Schema
@final
class StateSchema(TypedDict):
    """
    Schema for tracking monitoring states across different system components.
    """

    ceph_monitoring: str
    k8s_monitoring: str
    rms_state: RMS_STATES | None


# Zone Schema
@final
class ZoneDataSchema(TypedDict):
    """
    Schema for organizing zone-specific information about storage and compute nodes.
    """

    ceph_zones: cephNodesResultType
    k8s_zones: dict[str, list[NodeSchema]]


# Dynamic Data Schema
@final
class DynamicDataSchema(TypedDict):
    """
    Root schema for the dynamic configuration data used in RRS/RMS services.
    This schema represents the complete structure stored in the dynamic ConfigMap
    and encompasses all monitoring aspects of the system.
    """

    cray_rrs_pod: CrayRRSPod
    state: StateSchema
    timestamps: TimestampsSchema
    zone: ZoneDataSchema


# RMS API schemas


@final
class SCNSuccessResponse(TypedDict):
    """
    This represents the response body to a successful POST call to the /scn RMS endpoint.
    OAS: #/components/schemas/SCNSuccessResponse
    """

    message: Literal["POST call received"]


@final
class SCNBadRequestResponse(TypedDict):
    """
    This represents the response body to a POST call to the /scn RMS endpoint with bad data.
    OAS: #/components/schemas/SCNBadRequestResponse
    """

    error: Literal["Missing 'Components' or 'State' in the request"]


@final
class SCNInternalServerErrorResponse(TypedDict):
    """
    This represents the response body to an unsuccessful POST call to the /scn RMS endpoint.
    OAS: #/components/schemas/SCNInternalServerErrorResponse
    """

    error: Literal["Internal server error"]


@final
class ApiTimestampSuccessResponse(TypedDict):
    """
    This represents the response body to a successful POST call to the /api-ts RMS endpoint.
    OAS: #/components/schemas/ApiTimestampSuccessResponse
    """

    message: Literal["API timestamp updated successfully"]


@final
class ApiTimestampFailedResponse(TypedDict):
    """
    This represents the response body to an unsuccessful POST call to the /api-ts RMS endpoint.
    OAS: #/components/schemas/ApiTimestampFailedResponse
    """

    error: Literal["Failed to update API timestamp"]
