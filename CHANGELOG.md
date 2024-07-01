# Changelog

All notable changes to this project will be documented in this file.
The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).


## [Unreleased]

### Added

### Changed

### Removed

## [0.1.0] - 2024-07-01

Comment: First release

### Added

- Full support of particles using ASTRA generator binary
- Partial support of ASTRA simulations including the following modules: Cavities, Solenoids, Space charge
- Support of sequential and concurrent simulations based on OpenMPI
- Support of remote deployments via Docker and nginx
- API documentation via FastAPI and SwaggerUI
- Simple load balancing via nginx and docker replicas
- CRUD interface for generated particle distributions and simulation runs
- Support of API key authorization in production