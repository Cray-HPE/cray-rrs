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
from typing import TypedDict, Literal, final, Required

# Zones Schemas
################################################


@final
class KubernetesTopologyZoneSchema(TypedDict, total=False):
    """Schema for Kubernetes topology zone, including master and worker nodes."""

    Management_Master_Nodes: list[str]
    Management_Worker_Nodes: list[str]


@final
class CephZoneSchema(TypedDict, total=False):
    """Schema for Ceph zone, including storage nodes."""

    Management_Storage_Nodes: list[str]


@final
class ZoneItemSchema(TypedDict, total=False):
    """Schema for a single zone item, including its name and associated zones."""

    Zone_Name: Required[str]
    Kubernetes_Topology_Zone: KubernetesTopologyZoneSchema
    CEPH_Zone: CephZoneSchema


@final
class ZoneListSchema(TypedDict):
    """Schema for a list of zones."""

    Zones: list[ZoneItemSchema]


@final
class NodeSchema(TypedDict):
    """Schema for a node, including its name and status."""

    name: str
    status: str


@final
class StorageNodeSchema(TypedDict):
    """Schema for a storage node, including its name, status, and OSDs."""

    name: str
    status: str
    osds: dict[str, list[str]]


@final
class CephNodeInfo(TypedDict):
    """Schema representing a node containing OSDs."""

    name: str
    status: str
    osds: list[NodeSchema]


@final
class ManagementMasterSchema(TypedDict, total=False):
    """Schema for management master nodes in a Kubernetes topology zone."""

    Count: Required[int]
    Type: Required[Literal["Kubernetes_Topology_Zone"]]
    Nodes: list[NodeSchema]


@final
class ManagementWorkerSchema(TypedDict, total=False):
    """Schema for management worker nodes in a Kubernetes topology zone."""

    Count: Required[int]
    Type: Required[Literal["Kubernetes_Topology_Zone"]]
    Nodes: list[NodeSchema]


@final
class k8sNodes(TypedDict, total=False):
    """Schema for Kubernetes nodes, including masters and workers."""

    masters: list[NodeSchema]
    workers: list[NodeSchema]


@final
class ManagementStorageSchema(TypedDict, total=False):
    """Schema for management storage nodes in a Ceph zone."""

    Count: Required[int]
    Type: Required[Literal["CEPH_Zone"]]
    Nodes: list[StorageNodeSchema]


@final
class ZoneDescribeSchema(TypedDict, total=False):
    """Schema for describing a zone, including its name and management details."""

    Zone_Name: Required[str]
    Management_Master: ManagementMasterSchema
    Management_Worker: ManagementWorkerSchema
    Management_Storage: ManagementStorageSchema


# Critical Service Schemas
################################################


@final
class CriticalServiceEntrySchema(TypedDict, total=False):
    """Schema for a critical service entry, including its name, type, and status, balanced."""

    name: Required[str]
    type: Required[str]
    status: str
    balanced: str


@final
class CriticalServiceCmSchema(TypedDict, total=False):
    """Schema for a critical service entry, including its namespace, type, balanced and status."""

    type: Required[str]
    namespace: Required[str]
    status: str
    balanced: str


@final
class CriticalServicesItem(TypedDict, total=False):
    """Schema for critical services grouped by namespace."""

    namespace: dict[str, list[CriticalServiceEntrySchema]]


@final
class CriticalServicesListSchema(TypedDict, total=False):
    """Schema for a list of critical services."""

    critical_services: CriticalServicesItem


@final
class PodSchema(TypedDict):
    """Schema for a pod, including its name, status, node, and zone."""

    Name: str
    Status: str
    Node: str
    Zone: str


@final
class CriticalServiceDescribe(TypedDict, total=False):
    """Schema for describing a critical service, including its pods and instances."""

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
    """Schema for describing a critical service."""

    Critical_Service: CriticalServiceDescribe


@final
class CriticalServiceUpdateSchema(TypedDict):
    """Schema for updating critical services, including added and existing services."""

    Update: str
    Successfully_Added_Services: list[str]
    Already_Existing_Services: list[str]


# Error Response Schemas
@final
class ErrorDict(TypedDict):
    """Schema for error responses."""

    error: str


@final
class InformationDict(TypedDict):
    """Schema for informational responses."""

    Information: str
