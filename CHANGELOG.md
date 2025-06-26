# Changelog
All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

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
