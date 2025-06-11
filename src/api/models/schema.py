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

from typing import TypedDict, List, Dict, Literal


# Zones Schemas
################################################


class KubernetesTopologyZoneSchema(TypedDict, total=False):
    Management_Master_Nodes: List[str]
    Management_Worker_Nodes: List[str]


class CephZoneSchema(TypedDict, total=False):
    Management_Storage_Nodes: List[str]


class ZoneItemSchema(TypedDict, total=False):
    Zone_Name: str
    Kubernetes_Topology_Zone: KubernetesTopologyZoneSchema
    CEPH_Zone: CephZoneSchema


class ZoneListSchema(TypedDict, total=False):
    Zones: List[ZoneItemSchema]


# Zone Describe Schema


class NodeSchema(TypedDict, total=False):
    Name: str
    Status: str


class StorageNodeSchema(TypedDict, total=False):
    Name: str
    Status: str
    OSDs: Dict[str, List[str]]


class CephNodeInfo(TypedDict):
    """TypedDict representing a node containing OSDs."""

    Name: str
    Status: str
    Osds: List[NodeSchema]


class ManagementMasterSchema(TypedDict, total=False):
    Type: Literal["Kubernetes_Topology_Zone"]
    Nodes: List[NodeSchema]


class ManagementWorkerSchema(TypedDict, total=False):
    Type: Literal["Kubernetes_Topology_Zone"]
    Nodes: List[NodeSchema]


class k8sNodes(TypedDict, total=False):
    masters: List[NodeSchema]
    workers: List[NodeSchema]


class ManagementStorageSchema(TypedDict, total=False):
    Type: Literal["CEPH_Zone"]
    Nodes: List[StorageNodeSchema]


class ZoneDescribeSchema(TypedDict, total=False):
    Zone_Name: str
    Management_Masters: int
    Management_Workers: int
    Management_Storages: int
    Management_Master: ManagementMasterSchema
    Management_Worker: ManagementWorkerSchema
    Management_Storage: ManagementStorageSchema


# Critical Service Schemas
################################################


class CriticalServiceEntrySchema(TypedDict, total=False):
    name: str
    type: str


class CriticalServices(TypedDict, total=False):
    namespace: Dict[str, List[CriticalServiceEntrySchema]]


class CriticalServicesListSchema(TypedDict, total=False):
    critical_services: CriticalServices


class CriticalServiceDescribeSchema(TypedDict, total=False):
    Name: str
    Namespace: str
    Type: str
    Configured_Instances: int


class CriticalServiceStatusEntrySchema(TypedDict, total=False):
    name: str
    type: Literal["Deployment", "StatefulSet", "DaemonSet", "Pod"]
    status: Literal["Configured", "UnConfigured", "PartiallyConfigured"]
    balance: Literal["true", "false", "NA"]


class CriticalServicesStatus(TypedDict, total=False):
    namespace: Dict[str, List[CriticalServiceStatusEntrySchema]]


class CriticalServicesStatusListSchema(TypedDict, total=False):
    critical_services: CriticalServicesStatus


# Pod Schema
class PodSchema(TypedDict, total=False):
    Name: str
    Status: str
    Node: str
    Zone: str


class CriticalServiceStatusDescribeSchema(TypedDict, total=False):
    Name: str
    Namespace: str
    Type: Literal["Deployment", "StatefulSet", "DaemonSet"]
    Status: Literal["Configured", "UnConfigured", "PartiallyConfigured"]
    Balanced: Literal["true", "false", "NA"]
    Configured_Instances: int
    Currently_Running_Instances: int
    Pods: List[PodSchema]


class CriticalServiceUpdateSchema(TypedDict, total=False):
    Update: str
    Successfully_Added_Services: List[str]
    Already_Existing_Services: List[str]
