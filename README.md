[![License: CC BY-NC 4.0](https://img.shields.io/badge/License-CC_BY--NC_4.0-lightgrey.svg)](https://creativecommons.org/licenses/by-nc/4.0/)
[![DOI](https://zenodo.org/badge/DOI/10.5281/zenodo.12606498.svg)](https://doi.org/10.5281/zenodo.12606498)

# ASTRA Web API
This repository contains an API wrapper for the well-known [ASTRA simulation code](https://www.desy.de/~mpyflo/) by
K. Floettmann (DESY Hamburg) based on the Python FastAPI package and Docker.

# Startup

## Python dependencies

Install [uv](https://docs.astral.sh/uv/getting-started/installation/) and use
Python 3.14. Dependencies are declared in `pyproject.toml`; `uv.lock` records
exact versions and artifact hashes. The lock targets Python 3.14 and includes compatible FastAPI, Pydantic, and
scientific-library versions. `.python-version` selects Python 3.14 for local uv
commands. The previous Python 3.12 `venv` is not modified.

```bash
uv python install 3.14
uv sync --locked
uv run --locked pytest
```

uv creates a project `.venv`; the previous `venv` directory is not modified.
pytest belongs to the development group. Docker uses `uv sync --locked --no-dev`
to install only runtime dependencies. The Dockerfile pins uv to 0.12.21 and uses
an ASTRA/MPI base image. A BuildKit cache mount reuses downloads
between builds, and `/app/.venv/bin` is placed on PATH for `start.sh`.

The previous `requirements/requirements.txt` has been replaced by
`pyproject.toml` and `uv.lock`. Commit both files when changing dependencies.
Direct dependencies are pinned to exact versions; to upgrade one,
change its pin with `uv add "package==VERSION"` (use `--dev` for pytest), then run
the tests and a representative simulation before deploying. A stale lockfile
causes a locked build to fail rather than silently resolving new versions.

## Docker images

The base Dockerfile, `docker/images/astra-web.Dockerfile`, builds Open MPI 4.0.7
from a checksum-verified archive and downloads the three ASTRA executables
from DESY in separate stages. The final `python:3.14-slim-bookworm` image includes
ASTRA and MPI runtime files, without compilers, source trees, download tools,
Git, Nano, or Intel oneAPI. Current DESY binaries do not require shared Intel
libraries. The existing MPI compatibility symlink is retained; the build checks
ASTRA's shared libraries and symbols to catch changes in binary requirements.
MPI is installed with debug symbols stripped; headers, manual pages, and
pkg-config metadata are excluded. Runtime MPI plugins and help files remain.
The proxy uses the official `nginx:stable-alpine` image instead of the larger
default Debian variant.

Build the base on the same Docker context used for the API build, from the
repository root:

```bash
docker build --platform linux/amd64 \
  --file docker/images/astra-web.Dockerfile \
  --tag alexanderklemps/astra-web:astra-py314-2026-10-09 \
  docker/images

docker compose up -d --build
```

To build, tag, and push the base image to Docker Hub, authenticate first and
run the helper (it works from any working directory):

```bash
docker login --username alexanderklemps
./docker/images/build_push.sh astra-py314-2026-10-09
```

The optional second argument selects another Docker Hub repository, for example
`./docker/images/build_push.sh astra-custom yourname/astra-web`. The script uses
the selected Docker context and stops on any build, tagging, or push failure.
It publishes only the requested tag, without updating `latest` or deploying.

The API defaults to that Python 3.14 base tag. Rebuild the base before rebuilding
the API; older Python 3.12 base images do not satisfy the new lockfile. Set `ASTRA_BASE_IMAGE` for Compose or
pass `--build-arg BASE_IMAGE=your-base-tag` when building the API directly to
select another compatible base. The Linux ASTRA binaries require `linux/amd64`;
Compose explicitly selects that platform. `BUILD_JOBS` controls MPI compilation
parallelism (default 4).

The API uses uv 0.12.21 only during dependency installation via a BuildKit mount;
uv and its download cache are not included in the final API image. Only the
application package, startup script, dependency declarations, and installed
runtime dependencies are copied into it. Local data, `.env` files, and Git
metadata are excluded from the build context. Data directories are mounted by
the development and production Compose overrides.

`ASTRA_API_KEY` is required by Compose and passed as `API_KEY` at container
startup, not baked into an image. For a direct `docker run`, supply `API_KEY`
as an environment variable and mount `/app/data`. The startup script uses
`exec` so Uvicorn receives shutdown signals. Auto-reload is enabled only in the
development Compose override; production runs without a file watcher.

Python's base tag, Debian packages, and DESY download URLs are still mutable;
this is not a fully reproducible OS/binary lock. An uncached base build requires
network access and can retrieve newer ASTRA binaries. Both the base and API
images contain ASTRA, so the [DESY redistribution terms](https://www.desy.de/~mpyflo/)
apply; building these images does not grant permission to redistribute them.

MPI jobs run locally within each API container. Shared Compose sets
`OMPI_MCA_plm=^rsh` to disable Open MPI 4's SSH/RSH launcher; otherwise MPI can
fail at startup when the slim image has no SSH client. This is not multi-host
MPI configuration. For direct container or Uvicorn launches using Open MPI 4,
set the same environment variable. After updating Compose, recreate the API
container to apply it; no image rebuild is needed for this setting.
See the [Open MPI launcher discussion](https://github.com/open-mpi/ompi/issues/12386).

## Local deployment in development environment 

Build the image and start container by execution of the following command

    docker compose stop && docker compose up -d --build

The shared Compose file passes `ASTRA_MAX_MPI_PROCESSES` and
`ASTRA_MAX_CONCURRENT_JOBS` from `.env` into both development and production
containers (each defaults to 1). Set the MPI limit at least as high as the
requested `run_specs.thread_num`. After changing these settings, run Compose
`up -d` to recreate the API container; restarting it or Python auto-reload alone
does not update container environment variables. When running Uvicorn directly,
export these variables in its shell before starting it.

## Deployment in productive environment

In case you would like to deploy the API in a productive environment, say on a remote server, it is recommended to do
this via [Docker contexts](https://docs.docker.com/engine/context/working-with-contexts/).

Select your remote context with `docker context use YOUR_REMOTE_CONTEXT`, then
follow [Production deployment](#production-deployment) below. Production uses
local Compose builds and an explicitly selected persistent volume.

# API documentation

In case you are running the API server locally, you will find the interactive API documentation under

    http://localhost:8000/docs

## Debugging HTTP 422 responses

A 422 response means request validation failed before the endpoint ran. Read
the HTTP response body, not only the status line. Its `detail` list identifies
each invalid field with `loc` (including array indices), `msg`, and `type`:

```json
{
  "detail": [{
    "loc": ["body", "cavities", 0, "field_table"],
    "msg": "Field required",
    "type": "missing"
  }],
  "request_id": "a-generated-id"
}
```

For example, inspect `response.text` before calling `response.raise_for_status()`
in a Python HTTP client, or inspect the Response tab in your browser's Network
panel. The generated `request_id` is also returned in `X-Request-ID` and logged
with the method, path, and validation errors at WARNING level. Follow these logs:

```bash
docker compose logs --tail=100 -f api
```

Diagnostics omit submitted field values, raw bodies, error contexts, request
headers, and query strings. Validation messages and field names are retained;
custom validators should not embed submitted values in their error messages.
Authentication errors retain their existing 401 response. After changing the
handler, rebuild/restart the API container to enable the new diagnostics.

If ASTRA stops with `Lost reference particle` before bunch tracking, inspect
the aperture, optics, and RF settings. ASTRA normally aborts when the on-axis
or off-axis reference particle is lost. To match a reference input containing
`check_ref_part = False`, set `run_specs.check_reference_particle` to `false`.
The API defaults this setting to `true`; disabling it allows the run to proceed
past reference-particle loss but does not remove apertures or prevent bunch
losses. `output_specs.generate_reference_output` controls the diagnostic output
file independently and is not the switch for this abort condition.

# Convert an ASTRA input file to an API request

Using the project's Python environment, run:

```bash
uv run --locked python bin/parse_astra_input.py path/to/run.in
```

This writes `simulation_in.json` beside the input file, using the request structure
for `POST /simulations` or `PUT /simulations`. Choose another destination with
`-o path/to/simulation_in.json`. The script can be invoked from any working
directory and uses the project dependencies in `pyproject.toml` and `uv.lock`.

The converter maps ASTRA names to the API's input aliases and converts indexed
cavities, solenoids, quadrupoles, and apertures to lists ordered by their original indices.
Cavity and solenoid field maps are embedded as `field_table` objects containing
`z` and `v` arrays. Relative map paths resolve beside the input file; absolute
paths are read as supplied. Use `--field-map-dir path/to/maps` to relocate all
map references by filename, for example when importing a run from a container.
Field maps support two-column samples with or without an initial four-number
traveling-wave header (`z1 z2 n m`); that metadata is preserved in API JSON.

For cavities, `max_field_strength` is the peak on-axis electric field in **MV/m**
and maps directly to ASTRA's `MaxE`. The converter preserves that value (for
example, `MaxE = 58.1` becomes `max_field_strength: 58.1`). Interfaces displaying
this property should label it as an electric field in MV/m. Cavity voltage in MV
is a separate quantity; converting to it requires a defined field integration
and RF transit-time convention, rather than changing the unit label.

`Distribution = '/app/data/generator/beam.ini'` becomes
`run_specs.particle_file_name = 'beam'`. That distribution must already exist on
the API server; the converter does not upload particles. Use
`--particle-id registered-id` to select a different registered distribution.

The supported namelists are `NEWRUN`, `OUTPUT`, `CHARGE`, `CAVITY`, `SOLENOID`,
`QUADRUPOLE`, and `APERTURE`. Parsing accepts case-insensitive names, `!` comments,
comma or whitespace separators, quoted strings, Fortran logical values and `D`/`E`
exponents. Module assignments need individual positive indices such as `Phi(1)`;
circular grid radii use two indices, `Ap_GR(aperture, radius)`. Array slices,
repeated values, duplicate assignments/sections, and unsupported API settings
produce an error. Disabled module sections become empty lists.
Omitted settings use the API defaults, which may differ from native ASTRA defaults.

`Head` is omitted because the API regenerates it. Module IDs are reassigned by the
API, which may also sort modules by position. `L2D_3D` must agree with the presence
of `z_trans`. `high_accuracy` maps to `High_res`; `generate_reference_output`
independently maps to `RefS`, so differing values can be converted. Conversion
validates nested request models without creating run directories or launching a
simulation.

# API input names and null values

The request schema and converter use these names. Older aliases remain accepted
for existing clients, with the same units and values:

| Model | Public input name | Legacy input name | Unit |
| --- | --- | --- | --- |
| Run | `min_time_step` | `start_time` | ns |
| Run | `max_time_step` | `end_time` | ns |
| Cavity / solenoid | `z_offset` | `z_0` | m |
| Quadrupole | `z_center` | `z_0` | m |
| Quadrupole | `effective_length` | `q_len` | m |
| Quadrupole | `focusing_strength` | `q_focus` | m⁻² |
| Quadrupole | `fringe_taper_length` | `bore_radius` | m |

`z_offset` is added to field-map coordinates; `z_center` locates the quadrupole
centre. ASTRA attribute names, such as `C_pos` and `H_min`, are also accepted by
these request models. If multiple names for one field are supplied, their values
must agree. Unknown settings are rejected instead of silently using defaults.
ASTRA files continue to use the original ASTRA parameter names.

Output precision and reference output are separate settings:

```json
{"output_specs": {"high_accuracy": true, "generate_reference_output": false}}
```

`high_accuracy` now controls only `High_res`. Clients that previously relied on
`high_accuracy: false` also disabling `RefS` must explicitly send
`generate_reference_output: false`; its default is true.

Optional fields whose default is `None` accept JSON `null`. Optional numeric
settings, such as solenoid `max_field_strength`, `bunch_charge`, space-charge
grid overrides, and generator distribution widths, are omitted from ASTRA
output when null so ASTRA can use its own defaults. `z_trans: null` disables the
2D-to-3D transition. `sim_id: null` retains automatic directory naming;
`particle_file_name: null` retains the existing `example.ini` fallback, which
must exist on the server to run a simulation.

Cavities and solenoids require a non-null `field_table`. Quadrupoles require a
positive `effective_length` and a non-null `z_center`. Missing or null required
data is rejected during request validation, before a run directory is created.
Non-nullable numeric settings and booleans also reject null: it does not reset
them to their defaults. Defaults are validated against their declared types.

# Field-table formats

The `field_table` object accepts the existing two-column representation:

```json
{"z": [0.0, 0.05, 0.1, 0.15, 0.2], "v": [0.0, 1.0, -1.0, 1.0, 0.0]}
```

For a traveling-wave cavity, add the optional `traveling_wave` object:

```json
{
  "z": [0.0, 0.05, 0.1, 0.15, 0.2],
  "v": [0.0, 1.0, -1.0, 1.0, 0.0],
  "traveling_wave": {"z1": 0.050021029, "z2": 0.15006119, "n": 1, "m": 3}
}
```

These sample values illustrate the format; they are not a validated cavity field
profile. `z1` and `z2` are local field-map coordinates in metres, before applying
`z_offset`. The phase advance per cell is `2*pi*n/m`. A negative `n` describes a backward
wave. The header is metadata, not a field sample. See the
[ASTRA manual, section 6.9](https://www.desy.de/~mpyflo/Astra_manual/Astra-Manual_V3.2.pdf).

Both formats can be read and written through the same API model:

```python
from astra_web.simulation.schemas.tables import FieldTable

field_table = FieldTable.from_csv("cavity.dat")
request_data = field_table.model_dump(exclude_none=True)
restored = FieldTable.model_validate(request_data)
restored.to_csv("restored.dat")
```

`from_csv()` detects a four-number first nonempty, non-comment record as a TWS
header, then reads two-column samples. It accepts `1.0 3.0` for integer `n`/`m`,
Fortran `D` exponents, UTF-8 BOMs, and `!`/`#` comments. `to_csv()` restores the
header when present; omitting `traveling_wave` or setting it to null produces
only the original two-column format.

Cavity export automatically uses `TWS_C1_E.dat` when a header is present and
`C1_E.dat` otherwise, and the namelist references the same filename. The optional
cavity property `cell_count` maps to ASTRA's `C_numb` (cells excluding the input
and output couplers); it is separate from the header's phase-advance denominator.
For traveling-wave cavities, an omitted or null `cell_count` uses **120**, matching
the reference setup. This is a project default, not a universal ASTRA default;
set it explicitly for structures with a different number of cells. Ordinary
cavities still omit `C_numb` when no count is supplied. Traveling-wave requests
must satisfy `cell_count * n / m` being an integer; incompatible counts are
rejected during request validation instead of reaching ASTRA.
The converter delegates to `FieldTable.from_csv()`, so headers survive input-file
conversion, JSON validation, and simulation-file generation. Solenoids accept
ordinary field tables and reject traveling-wave metadata.

Validation requires at least two finite samples, matching column lengths,
strictly increasing `z`, ordered header boundaries within the sampled interval,
nonzero integer `n`, and positive integer `m`. This validates the file structure;
it does not check field periodicity or derivatives required by ASTRA's TWS model.
Other map formats, including 3D maps, remain unsupported by the converter.

# Apertures

Add `apertures` to a simulation request. A contour uses `z` in **metres** and
`radius` in **millimetres**:

```json
{
  "apertures": [
    {
      "type": "table",
      "z_offset": 1.0,
      "aperture_table": {
        "z": [0.0, 0.1, 0.1, 0.2],
        "radius": [5.0, 5.0, 2.0, 2.0]
      }
    },
    {"type": "RAD", "z_start": 0.5, "z_end": 0.51, "radius": 2.0}
  ]
}
```

`type` defaults to `table`. Unlike a field table, an aperture contour allows
repeated `z` values for radial steps. Values must be finite, radii nonnegative,
column lengths equal, and `z` nondecreasing with a positive total extent.
`ApertureTable.from_csv(path)` and `.to_csv(path)` read and write two-column
contours, including Fortran `D` exponents and `!`/`#` comments on import. Aperture
tables do not take a traveling-wave header.

Built-in geometries use `z_start < z_end` in metres and these case-insensitive
types, following the [ASTRA manual, section 6.7](https://www.desy.de/~mpyflo/Astra_manual/Astra-Manual_V3.2.pdf):

| Type | Geometry parameter, in millimetres |
| --- | --- |
| `RAD` | `radius`: positive for a hole, negative for a cylindrical plug |
| `Scr_X`, `Scr_Y` | `radius`: signed scraper distance from the axis |
| `Col_X`, `Col_Y` | `radius`: positive half gap |
| `Cir` | `grid_radii`: inner/outer radius pairs, e.g. `[0, 1, 2, 3]` |

Grid rings must be ordered, non-overlapping, and have positive width; up to 20
rings are accepted. Keyword geometries cannot also supply a table. For all types,
`z_offset` shifts the local longitudinal coordinates; `x_offset` and `y_offset`
are in metres. `xz_rotation`, `yz_rotation`, and `xy_rotation` are in radians and
map to ASTRA's `A_xrot`, `A_yrot`, and `A_zrot`, respectively.

The API sorts apertures by their shifted start positions, assigns IDs, writes
`A{id}.dat` for contours, and generates `&APERTURE` with `LApert` enabled whenever
the list is nonempty. Aperture-only simulations are accepted. Omit `apertures` or
send an empty list to disable them.

`bin/parse_astra_input.py` imports `APERTURE`, embeds contour files, and preserves
keyword geometry, offsets, rotations, and circular-grid radii. Relative paths
resolve beside the input; `--field-map-dir` also relocates aperture tables by
basename. Grid radius indices must be consecutive from 1. Secondary-emission
settings and aperture loop controls are not yet supported and cause conversion
errors when the aperture section is enabled.

# Troubleshooting

### Problem: Rootless containers on the remote host quit once the user terminates the ssh session.
    
This is not an issue of Docker. Linux stops processes started by a normal user if loginctl is configured to not use 
lingering, to prevent normal users to keep long-running processes executing in the system.
In order to fix the problem, one can enable lingering by executing 

    loginctl enable-linger $UID

on the remote host.
Source: [Stackoverflow](https://stackoverflow.com/a/73312070)

# Cite this project

If you use this project in your scientific work and find it useful, you could use the following BibTeX entry to cite this project.

      @misc{astra-web,
        Author = {A. Klemps},
        Title = {ASTRA-Web},
        Year = {2024},
        publisher = {GitHub},
        version = {0.1.0},
        doi = {10.5281/zenodo.12606498},
        url = {https://doi.org/10.5281/zenodo.12606498}
      }

## Production deployment

Use Docker Compose v2. Production builds the API from `docker/api.Dockerfile`
and the proxy from `docker/nginx.Dockerfile` using the local checkout. Published
API/proxy images and `ASTRA_API_IMAGE` / `ASTRA_NGINX_IMAGE` are not required.
The API inherits its build configuration from the shared Compose file and uses
`ASTRA_BASE_IMAGE` (a Python 3.14 ASTRA/MPI base image). That base image must be
available locally on the selected Docker context or pullable from its registry.

Use `docker/production.env.example` as a template, or add its settings to your
existing `.env`. Set `ASTRA_DATA_VOLUME` to your actual existing volume name.
From the repository root, using `.env`:

```bash
docker compose --env-file .env -f docker/docker-compose.yml -f docker/docker-compose.production.yml config --quiet
docker compose --env-file .env -f docker/docker-compose.yml -f docker/docker-compose.production.yml up -d --build --wait
```

These are commands for you to run when ready to build and deploy. For a separate
`production.env`, replace `--env-file .env` with `--env-file production.env`.
Both filenames are excluded from Git and the Docker build context. Keep any
other credential-file names outside version control as well.
The production file is an override: always combine it with the shared file,
never with the development override. Record the deployed commit and base-image
reference, and retain known-good images before rebuilding for rollback.

Defaults are two replicas, 2 GiB memory per replica, and one running
ASTRA/generator job per API process. Busy processes return HTTP 503 with
`Retry-After: 5`; clients should retry with backoff. Simulation `thread_num`
cannot exceed `ASTRA_MAX_MPI_PROCESSES` (default 1). Choose limits from measured
workloads: replicas times concurrent jobs times MPI processes should fit the
host's available CPUs, leaving capacity for the host and proxy. Docker CPU
quotas are omitted for hosts without CPU CFS/cgroup support; application
concurrency limits do not impose a hard CPU quota.
Run one Uvicorn worker per container; these limits are per process. Native
OpenMP/OpenBLAS threads are limited to one in production. This is bounded
in-process execution, not a persistent job queue; deployments can interrupt jobs.

`/healthz` is unauthenticated and tests API responsiveness. Simulation and
generator work runs outside the event loop, and cancelled requests retain their
job slot until the worker finishes. Health does not certify ASTRA binaries or
available disk space. Compose waits for healthy API containers before starting
Nginx; health failures alone do not trigger container restarts. Nginx refreshes
Docker DNS every 10 seconds to discover replacement API containers.

HTTP now binds to `127.0.0.1:8080` by default. Place an HTTPS reverse proxy on the
Docker host in front of it, preserving the `/astra/` prefix. If the TLS proxy is
on another host, bind to a private interface and restrict access to that proxy.
A proxy in another container needs shared-network connectivity instead of the
host's loopback address. Do not expose API-key traffic over public plain HTTP.
This setup does not provision certificates or an external TLS proxy.

Set `ASTRA_DATA_VOLUME` to the **existing** Docker volume name when upgrading;
inspect volume names before deployment. The volume is external, so Compose does
not create or remove it. For a new installation, provision it once with
`docker volume create astra-production-data` and set the matching name. All
replicas on this single Docker host share `/app/data`. Multi-host deployment
requires shared storage and is not covered by this configuration.

Back up the volume to separate storage on a regular schedule and before updates.
For a consistent backup, block new submissions, let jobs finish, stop the API,
then archive the entire volume (generator inputs and simulation directories).
Restore into a separate volume and verify representative results before switching
`ASTRA_DATA_VOLUME`. Keep daily backups for 7 days and weekly backups for 4 weeks
as an initial policy; adjust to storage capacity and scientific reproducibility
requirements. Simulation retention is manual: archive completed runs before
using the API's delete endpoints; never prune active runs. Monitor disk usage.
Container logs use the `local` driver with five 10 MiB files per container.

## Global RF phase shift

Set `run_specs.global_rf_phase_shift` in degrees to export ASTRA's global
`Phi(0)` setting in `&CAVITY`:

```json
{
  "run_specs": {
    "global_rf_phase_shift": -10.0
  }
}
```

This setting belongs to the API's run specifications but is not written into
`&NEWRUN`. Individual cavity `phase` values remain unchanged; ASTRA applies the
global shift. Omitted or `null` values omit `Phi(0)`; explicit zero writes
`Phi(0) = 0.0`. Finite negative values and values outside 0–360 degrees are
accepted without normalization. The input converter imports `&CAVITY.Phi(0)`
into this run setting, and simulation metadata records it in `input.json`.

This does not convert measured RF-channel phase references or change
`auto_phase`. Keep the selected phase convention consistent with your input;
see the [ASTRA manual](https://www.desy.de/~mpyflo/Astra_manual/Astra-Manual_V3.2.pdf).

## Named simulations and particle snapshots

`run_specs.sim_id` selects both the simulation ID and its directory under
simulation storage. For example, `"sim_id": "1pCTripleOnCrest"` returns
`"sim_id": "1pCTripleOnCrest"`; retrieve results with
`GET /simulations/1pCTripleOnCrest` (under `/astra` in production).
The legacy input name `run_specs.run_dir` remains accepted. Supplying both
names with different values is rejected. Internally, `run_dir` denotes the
resolved filesystem path.
Omit `sim_id` or send `null` to generate a dated ID. Names must start with an ASCII
letter or digit, contain only letters, digits, dots, underscores and hyphens,
and be at most 128 characters. Reusing an existing name returns HTTP 409 and
preserves that run; choose a fresh name for each submission.

Particle outputs are packed into `snapshots.parquet` in the simulation's own
directory. Raw files are removed only after the complete archive is successfully
closed and published. Both POST's immediate results and later GET requests read
that archive. For existing runs affected by the previous custom-directory bug,
GET and statistics can read surviving raw `run.<position>.001` outputs even if
no archive exists; use the actual directory name as the ID. No data migration
or rerun is needed when those raw files remain available.

If ASTRA produced no particle snapshots (for example, tracking stopped before a
checkpoint or particle output was disabled), GET returns `particles: []` together
with the available run output instead of failing on a missing archive.
Statistics require snapshots and return HTTP 409 with an explanation when none
are available. Check `run.out` to distinguish a completed run from an ASTRA early
stop; this fallback cannot reconstruct particle data ASTRA never produced.
