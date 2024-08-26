# Changelog

All notable changes to this project will be documented in this file.
The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

Summary: Many convenience changes. Updated ASTRA version.

### Added

- Inclusion of both sequential and concurrent ASTRA binaries.
- Concurrency is toggled by value of "thread_num" in the simulation request parameters.
- Dump of simulation input to json file for later reference.

### Changed

- Structure of schemas. Models have been distributed to separate files.
- Initial particle distribution contained in data/generator is now symlinked in simulation folder.
- Update to new sequential ASTRA version (July 2024). Base image has been updated too (astra-web:astra-07-24), including
  Intel-Fortran-Compiler since new ASTRA version depends on it. 
- ASTRA binaries have been moved from runtime image to base image for more stability.
- New ASTRA binary path in container is now /usr/local/lib
- Added start.sh in base path, setting environment variables before starting uvicorn server.

### Removed

- Environment variable "ENABLE_CONCURRENCY" in dockerfiles
- Path environment variables in api.Dockerfile due to inclusion of both ASTRA binaries
- ASTRA binary installation removed from api dockerfile.

## [0.1.0] - 2024-07-01

Summary: First release

### Added

- Full support of particles using ASTRA generator binary
- Partial support of ASTRA simulations including the following modules: Cavities, Solenoids, Space charge
- Support of sequential and concurrent simulations based on OpenMPI
- Support of remote deployments via Docker and nginx
- API documentation via FastAPI and SwaggerUI
- Simple load balancing via nginx and docker replicas
- CRUD interface for generated particle distributions and simulation runs
- Support of API key authorization in production