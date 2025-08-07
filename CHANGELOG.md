# Changelog
All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [1.0.4] - 2025-08-07
### Fixed
CASM-5675: The length of zone name to be fixed
- The length of the name to be fixed. Since the zone name is a label, as per Kubernetes standards, the name should be 1-63.
 
## [1.0.3] - 2025-08-04
### Fixed
- CASM-5499: Conditional enablement of RRS (Rack Resiliency Service)
    - RRS init to sleep till the Rack Resiliency is enabled and setup with Kubernetes and Ceph zones.
        
## [1.0.2] - 2025-07-24
### Fixed
- CASMTRIAGE-8508 - Critical Services balanced staus is not shown correctly by RMS
    - Fixed to show the balanced status of Critical Services by RMS as appropriate when the pods are
      not distributed across racks properly due to kubernetes scheduler failure. 
        
## [1.0.1] - 2025-06-26
### Fixed
- Update the annotations in `Chart.yaml` so they point to the correct Docker images

## [1.0.0] - 2025-05-26
### Added
CASM-4874, CASM-4875 and CASM-4876: Implementation of the Rack Resiliency Service (RRS) and deployment model

- Includes RRS changes: RRS is part of Rack Resiliency feature which includes 3 containers:
    - Init container to perform required initialization for RRS
    - RMS container to monitor critical services, ceph status and k8s/CEPH zone placements
    - API container providing backend for RRS module of cray CLI
- Includes RRS deployment changes: RRS is deployed as cray-rrs service via helm chart
