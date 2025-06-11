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
from typing import TypedDict, List, Dict, Literal

# Zones Schemas
################################################


class KubernetesTopologyZoneSchema(TypedDict, total=False):
    """Schema for Kubernetes topology zone, including master and worker nodes."""

    Management_Master_Nodes: List[str]
    Management_Worker_Nodes: List[str]


class CephZoneSchema(TypedDict, total=False):
    """Schema for Ceph zone, including storage nodes."""

    Management_Storage_Nodes: List[str]


class ZoneItemSchema(TypedDict, total=False):
    """Schema for a single zone item, including its name and associated zones."""

    Zone_Name: str
    Kubernetes_Topology_Zone: KubernetesTopologyZoneSchema
    CEPH_Zone: CephZoneSchema


class ZoneListSchema(TypedDict, total=False):
    """Schema for a list of zones."""

    Zones: List[ZoneItemSchema]


# Zone Describe Schema
################################################


class NodeSchema(TypedDict, total=False):
    """Schema for a node, including its name and status."""

    name: str
    status: str


class StorageNodeSchema(TypedDict, total=False):
    """Schema for a storage node, including its name, status, and OSDs."""

    name: str
    status: str
    osds: Dict[str, List[str]]


class CephNodeInfo(TypedDict):
    """Schema representing a node containing OSDs."""

    name: str
    status: str
    osds: List[NodeSchema]


class ManagementMasterSchema(TypedDict, total=False):
    """Schema for management master nodes in a Kubernetes topology zone."""

    Type: Literal["Kubernetes_Topology_Zone"]
    Nodes: List[NodeSchema]


class ManagementWorkerSchema(TypedDict, total=False):
    """Schema for management worker nodes in a Kubernetes topology zone."""

    Type: Literal["Kubernetes_Topology_Zone"]
    Nodes: List[NodeSchema]


class k8sNodes(TypedDict, total=False):
    """Schema for Kubernetes nodes, including masters and workers."""

    masters: List[NodeSchema]
    workers: List[NodeSchema]


class ManagementStorageSchema(TypedDict, total=False):
    """Schema for management storage nodes in a Ceph zone."""

    Type: Literal["CEPH_Zone"]
    Nodes: List[StorageNodeSchema]


class ZoneDescribeSchema(TypedDict, total=False):
    """Schema for describing a zone, including its name and management details."""

    Zone_Name: str
    Management_Masters: int
    Management_Workers: int
    Management_Storages: int
    Management_Master: ManagementMasterSchema
    Management_Worker: ManagementWorkerSchema
    Management_Storage: ManagementStorageSchema


# Critical Service Schemas


class CriticalServiceEntrySchema(TypedDict, total=False):
    """Schema for a critical service entry, including its name, type, and status."""

    name: str
    type: str
    status: str
    balanced: str


class CriticalServicesItem(TypedDict, total=False):
    """Schema for critical services grouped by namespace."""

    namespace: Dict[str, List[CriticalServiceEntrySchema]]


class CriticalServicesListSchema(TypedDict, total=False):
    """Schema for a list of critical services."""

    critical_services: CriticalServicesItem


# Pod Schema
class PodSchema(TypedDict, total=False):
    """Schema for a pod, including its name, status, node, and zone."""

    Name: str
    Status: str
    Node: str
    Zone: str


class CriticalServiceDescribe(TypedDict, total=False):
    """Schema for describing a critical service, including its pods and instances."""

    Name: str
    Namespace: str
    Type: str
    Status: str
    Balanced: str
    Configured_Instances: int | None
    Currently_Running_Instances: int
    Pods: List[PodSchema]


class CriticalServiceDescribeSchema(TypedDict, total=False):
    """Schema for describing a critical service."""

    Critical_Service: CriticalServiceDescribe


class CriticalServiceUpdateSchema(TypedDict, total=False):
    """Schema for updating critical services, including added and existing services."""

    Update: str
    Successfully_Added_Services: List[str]
    Already_Existing_Services: List[str]
    error: str
