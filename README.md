[![License: CC BY-NC 4.0](https://img.shields.io/badge/License-CC_BY--NC_4.0-lightgrey.svg)](https://creativecommons.org/licenses/by-nc/4.0/)
[![DOI](https://zenodo.org/badge/DOI/10.5281/zenodo.12606498.svg)](https://doi.org/10.5281/zenodo.12606498)

# ASTRA Web API
This repository contains an API wrapper for the well-known [ASTRA simulation code](https://www.desy.de/~mpyflo/) by
K. Floettmann (DESY Hamburg) based on the Python FastAPI package and Docker.

# Startup

## Python dependencies

Install [uv](https://docs.astral.sh/uv/getting-started/installation/) and use
Python 3.12. Dependencies are declared in `pyproject.toml`; `uv.lock` records
exact versions and artifact hashes. The initial lock preserves all 38 package
versions from the existing local `venv`, including transitive dependencies.
The lock also includes a conditional Windows dependency that is not installed
on Linux. This baseline has not been compared with a running production image.

```bash
uv sync --locked
uv run --locked pytest
```

uv creates a project `.venv`; the previous `venv` directory is not modified.
pytest belongs to the development group. Docker uses `uv sync --locked --no-dev`
to install only runtime dependencies. The Dockerfile pins uv to 0.12.21 and keeps
the existing ASTRA/Intel/MPI base image. A BuildKit cache mount reuses downloads
between builds, and `/app/.venv/bin` is placed on PATH for `start.sh`.

The previous `requirements/requirements.txt` has been replaced by
`pyproject.toml` and `uv.lock`. Commit both files when changing dependencies.
Direct dependencies are initially pinned to the working versions; to upgrade one,
change its pin with `uv add "package==VERSION"` (use `--dev` for pytest), then run
the tests and a representative simulation before deploying. A stale lockfile
causes a locked build to fail rather than silently resolving new versions.

## Local deployment in development environment 

Build the image and start container by execution of the following command

    docker compose stop && docker compose up -d --build

## Deployment in productive environment

In case you would like to deploy the API in a productive environment, say on a remote server, it is recommended to do
this via [Docker contexts](https://docs.docker.com/engine/context/working-with-contexts/).

Uncomment the COMPOSE_FILE environment variable in the .env file contained within this project an run

    docker context use [YOUR_REMOTE_CONTEXT]
    docker compose stop && docker compose up -d --build

# API documentation

In case you are running the API server locally, you will find the interactive API documentation under

    http://localhost:8000/docs

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
cavities, solenoids, and quadrupoles to lists ordered by their original indices.
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

The supported namelists are `NEWRUN`, `OUTPUT`, `CHARGE`, `CAVITY`, `SOLENOID`, and
`QUADRUPOLE`. Parsing accepts case-insensitive names, `!` comments, comma or
whitespace separators, quoted strings, Fortran logical values and `D`/`E`
exponents. Module assignments need individual positive indices such as `Phi(1)`;
array slices, repeated values, duplicate assignments/sections, and unsupported
API settings produce an error. Disabled module sections become empty lists.
Omitted settings use the API defaults, which may differ from native ASTRA defaults.

`Head` is omitted because the API regenerates it. Module IDs are reassigned by the
API, which may also sort modules by position. `L2D_3D` must agree with the presence
of `z_trans`. The current API uses `high_accuracy` for both `High_res` and `RefS`,
so differing values cannot be converted. The current simulation creation code
also assumes at least one cavity and one solenoid; converting empty lists does
not fix that server limitation. Conversion validates nested request models
without creating run directories or launching a simulation.

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
`z_0`. The phase advance per cell is `2*pi*n/m`. A negative `n` describes a backward
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
The converter delegates to `FieldTable.from_csv()`, so headers survive input-file
conversion, JSON validation, and simulation-file generation. Solenoids accept
ordinary field tables and reject traveling-wave metadata.

Validation requires at least two finite samples, matching column lengths,
strictly increasing `z`, ordered header boundaries within the sampled interval,
nonzero integer `n`, and positive integer `m`. This validates the file structure;
it does not check field periodicity or derivatives required by ASTRA's TWS model.
Other map formats, including 3D maps, remain unsupported by the converter.

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
