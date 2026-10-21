# Repository review log

Reviewed: 2026-09-29

Scope: the current working tree, including existing staged and unstaged changes, across the API, authentication, schemas, serialization, simulation execution, statistics, maintenance scripts, and deployment configuration. Findings describe this working tree, not necessarily the last commit. Application code and existing user changes were left unchanged.

Priority: **P1** = address first because of unauthorized access, data loss, or major availability failures; **P2** = functional correctness or operational reliability issue. “Reproduced” means checked locally with synthetic inputs, temporary directories, or mocks. Other findings are based on the cited code paths.

## Findings

### 1. P1 — Authentication succeeds when API_KEY is unset

- **Location:** `astra_web/auth/auth_schemes.py:5–10`.
- `API_KEYS` becomes `[None]` when the environment variable is missing. The optional header dependency also returns `None` for a missing header, so the membership check accepts an unauthenticated request.
- **Evidence:** reproduced both by calling the dependency and through an ASGI request: `GET /particles` without a header returned HTTP 200 with the missing-key configuration.
- **TODO:** reject missing/empty configuration at startup and always reject absent credentials. Add tests for missing configuration, absent headers, incorrect keys, and valid keys.

### 2. P1 — User-controlled identifiers are not confined to the data directories

- **Location:** `astra_web/main.py:143–156`, `astra_web/utils.py:24–33`, `astra_web/simulation/schemas/run.py:61–65`, `astra_web/simulation/statistics.py:18–21`.
- Identifiers are interpolated or joined into filesystem paths without validation or a containment check. In particular, the simulation deletion handler accepts `..` and passes the parent of the simulation directory to recursive deletion. Statistics IDs supplied in JSON can also contain path separators; particle input names can traverse out of their intended directory.
- **Evidence:** invoking the deletion handler with `..` and a mocked `rmtree` reached `rmtree('/tmp/<review-directory>/..')`. With the repository defaults, the analogous target resolves to the shared `data` directory. No real deletion was performed. HTTP reachability of a literal dot segment can depend on proxy/client normalization; the handler itself is unsafe.
- **TODO:** validate IDs centrally, reject dot segments and separators, resolve paths and enforce containment, account for symlinks, and prohibit deleting a storage root or its parents. Apply this to every read/write/delete entry point, including JSON IDs.

### 3. P1 — Snapshot compaction deletes inputs before the archive is safely committed

- **Location:** `astra_web/simulation/simulation.py:40–56`, `bin/squash_particle_snapshots.py:18–33`.
- Each source is unlinked immediately after `write_table`, while the Parquet footer is only completed on `close`. There is no exception-safe close, temporary archive, or atomic publication. A crash, disk error, or later schema mismatch can leave an incomplete archive after earlier source files have been deleted. An existing archive is opened for replacement before success is known.
- **Evidence:** two valid ten-column synthetic snapshots, one with decimal tokens and one with integer tokens, inferred different Arrow schemas. The second write raised `ValueError`; the first source file had already been deleted.
- **TODO:** declare a stable schema, write to a temporary file with exception-safe cleanup, close and validate it, atomically publish it, and only then remove sources. Define safe retry and existing-archive behavior. Test a failure after the first successful row group.

### 4. P1 — Default and module-free simulation requests crash during validation

- **Location:** `astra_web/simulation/schemas/io.py:102–115,129–146`.
- Cavities and solenoids default to empty lists, but `model_post_init` unconditionally accesses `self.solenoids[0]` and `self.cavities[0]`. A drift-only, quadrupole-only, or otherwise valid request omitting either module type raises `IndexError`. Directory creation happens first, leaving an orphan run directory and potentially an empty `input.json`.
- **Evidence:** `SimulationInput()` raised `IndexError` in an isolated storage directory and left a directory behind.
- **TODO:** support empty module lists when recording inputs, or explicitly validate any actual mandatory modules. Move filesystem side effects out of model construction and into the execution lifecycle after validation. Test empty and single-module-type configurations.

### 5. P1 — Long synchronous work blocks the API event loop

- **Location:** `astra_web/main.py:100–123,159–165`, `astra_web/simulation/simulation.py:21–35`.
- The simulation and statistics handlers are `async def`, but directly call synchronous subprocess, filesystem, Pandas, and analysis operations. A simulation waiting in `subprocess.run` blocks other requests handled by the same worker, potentially for the default 600 seconds. Multiple replicas reduce the scope but do not remove the defect.
- **TODO:** offload blocking work through synchronous handlers or an executor. For long simulations, consider a bounded job queue and explicit job status. Test that a slow simulation does not prevent a lightweight request from completing.

### 6. P1 — Deployment embeds credentials in the image

- **Location:** `docker/docker-compose.yml:6–8`, `docker/api.Dockerfile:10–16`, `.dockerignore:1–5`; tracked `.env`.
- The API key is a build argument persisted as an image environment variable, making it available to anyone able to inspect or pull that image. `COPY .. /app` also includes `.env` and `.git` because neither is excluded by `.dockerignore`. The local `.env` is tracked despite its `.gitignore` entry; ignoring an already tracked file does not remove it from version control.
- **Evidence:** verified the Docker configuration and that `git ls-files .env` returns `.env`. Secret values were not read or included in this report; whether real credentials have been published was not assessed.
- **TODO:** supply credentials at runtime, exclude environment files and Git metadata from the build context, and use a tracked template with placeholders. Check whether distributed images or repository history contain real credentials and rotate any exposed keys.

### 7. P2 — POST simulation responses lose all particle snapshots after compaction

- **Location:** `astra_web/simulation/simulation.py:35,53`, `astra_web/main.py:109–119`.
- Processing now compacts and deletes the raw snapshots, but `POST /simulations` still populates `particles` by globbing those raw files. Successful runs therefore return an empty particle list. The GET endpoint uses the new Parquet reader, so the two endpoints disagree.
- **Evidence:** after compacting two synthetic snapshots, the GET loader returned two distributions and the POST handler returned zero with execution mocked.
- **TODO:** share the result-loading implementation between POST and GET. Add a regression test asserting identical particle data through both routes.

### 8. P2 — Configurable run numbers are ignored by output readers

- **Location:** `astra_web/simulation/schemas/run.py:44–47`, `astra_web/utils.py:28–29`, `astra_web/simulation/simulation.py:84–89`, `bin/squash_particle_snapshots.py:14–15`.
- The request accepts `run_number` and exports it to ASTRA, while snapshot globs and emittance filenames hard-code `.001`. A run using another number is not found by the readers or compactor and can subsequently fail when Parquet is missing.
- **TODO:** propagate the run number into every output path, or restrict the schema to the single supported value. Test a non-default run number.

### 9. P2 — Result loading requires Parquet even when particle output is disabled

- **Location:** `astra_web/simulation/schemas/io.py:69–72`, `astra_web/simulation/simulation.py:40–56,94–102`, `astra_web/utils.py:32–33`.
- A request may disable complete particle output, in which case compaction creates no archive. GET still unconditionally reads `snapshots.parquet`, resulting in an unhandled `FileNotFoundError`. Existing runs containing only raw snapshots have the same compatibility problem. The route checks only whether the run directory exists, which does not establish that the run completed.
- **Evidence:** a synthetic run with `run.in` and `run.out`, but no snapshots, failed in `load_simulation_output` with `FileNotFoundError`.
- **TODO:** distinguish absent optional output, legacy storage, failed runs, and corrupt output. Return empty/optional particle data when appropriate, support a migration/fallback policy, and expose a clear run status.

### 10. P2 — External process failures are treated as successful results

- **Location:** `astra_web/generator/generator.py:19–30`, `astra_web/simulation/simulation.py:21–37`.
- Both wrappers discard the return code and stderr and consume only stdout. A failing executable can appear successful, while simulation compaction still proceeds on partial files. Simulation timeouts are uncaught; generator execution has no timeout.
- **Evidence:** mocked subprocess results with return code 1 and stderr `failed` caused both wrappers to return an empty success value without raising an error.
- **TODO:** check exit status, retain diagnostic stderr, map process failures and timeouts to explicit API/job errors, bound generator runtime, and avoid publishing incomplete results. Verify MPI child cleanup on timeout in an integration environment.

### 11. P2 — Silent float32 conversion reduces particle precision

- **Location:** `astra_web/generator/schemas/particles.py:58–61`, `astra_web/simulation/simulation.py:45–46`.
- Uploaded particles and compacted snapshots are silently downcast from float64 to float32. Printing twelve decimal digits afterward cannot restore lost precision. This also undermines the exposed `high_accuracy` setting and differs from the standalone migration script, which preserves float64 values.
- **Evidence:** a CSV round trip changed a reference `pz` value of `10000000.1234` to `10000000.0`.
- **TODO:** retain float64 by default or make lossy storage explicit with documented tolerances. Add numerical round-trip tests covering large reference momenta and small offsets.

### 12. P2 — Modules can reference field-map files that were never written

- **Location:** `astra_web/simulation/schemas/modules.py:25–36,73–85,98–109,133–142`.
- Cavities and solenoids accept omitted `field_table` values, always export `File_Efield`/`File_Bfield`, and silently skip writing the corresponding file when the table is absent. In a newly created run directory those references point to nonexistent files.
- **Evidence:** a simulation containing default cavity and solenoid objects exported the filenames, but neither `C1_E.dat` nor `S1_B.dat` existed after `write_to_disk`.
- **TODO:** require a valid field table for modes that need it, or explicitly support and validate an alternative field source before execution.

### 13. P2 — Particle conversion discards species and individual times

- **Location:** `astra_web/generator/schemas/particles.py:88–100`; supported generator species in `astra_web/generator/schemas/enums.py:14–18`.
- `to_pmd` always sets species to `electron`, although the generator supports other species and the particle schema includes species codes. It calculates per-particle `t_clock` values, then supplies the scalar reference time as `t`, discarding the individual times. Statistics derived through this conversion can therefore use the wrong species and lose time spread.
- **Evidence:** a two-row distribution with species code 3 converted to `electron`; distinct clock values `[2, 3]` became identical times `[2e-9, 2e-9]`.
- **TODO:** map and validate species, define mixed-species behavior, and supply the correctly converted per-particle time array. Test supported species and a nonzero time spread. Also replace `data.size` with the row count if `n_particles` metadata is retained.

### 14. P2 — Schema validation accepts inputs that fail later or consume unbounded resources

- **Location:** `astra_web/generator/schemas/particles.py:10–61`, `astra_web/simulation/schemas/tables.py:8–19`, `astra_web/generator/schemas/io.py:32–36`, `astra_web/simulation/schemas/io.py:197–201`, `astra_web/simulation/schemas/run.py:26–42`.
- Particle columns and field-table columns are not checked for equal lengths. Negative particle counts and slice counts are accepted. Thread counts have no upper bound, and timeout values have no positive lower bound or operational cap. Malformed data reaches Pandas or the external executables instead of being rejected at the API boundary.
- **Evidence:** `Particles(x=[1])` and unequal field-table columns passed model construction but raised `ValueError` during CSV writing. `particle_count=-1` and `n_slices=-1` were accepted.
- **TODO:** validate consistent/nonempty columns where required, positive counts, finite values, and related range constraints. Establish server-side limits for particle counts, slices, thread counts, and runtime. Return validation errors before filesystem changes or process launch.

### 15. P2 — Saved simulation inputs are insufficient to reproduce a run

- **Location:** `astra_web/simulation/schemas/io.py:133–146`, `astra_web/simulation/statistics.py:18–19,38`.
- `input.json` now records only six hand-picked values from the first cavity/solenoid and selected run settings. It loses other modules, output settings, space charge, field tables, and much of the run configuration. The statistics response exposes that incomplete object as `inputs`.
- **TODO:** persist a complete, versioned input representation alongside any derived summary. Preserve field maps and initial-distribution identity/content as needed for reproducibility. Do not assume ordinary `model_dump` is sufficient: excluded fields and the custom ASTRA serializers need explicit handling.

### 16. P2 — One API alias controls two unrelated output options

- **Location:** `astra_web/simulation/schemas/io.py:46–55`.
- Both `High_res` and `RefS` use `validation_alias='high_accuracy'`. Clients cannot independently control precision and reference-trajectory output through that alias, and disabling precision unexpectedly disables the trajectory output too.
- **Evidence:** `SimulationOutputSpecification(high_accuracy=False)` set both fields to `False`.
- **TODO:** assign a distinct public alias to `RefS` and test independent values. Define compatibility behavior for existing clients.

### 17. P2 — Standalone snapshot migration silently skips the first matching file

- **Location:** `bin/squash_particle_snapshots.py:18–19`.
- The migration drops the first glob result using `[1:]`, apparently assuming it is the initial-distribution link. The simulation path currently does not create that link (`astra_web/simulation/simulation.py:22`). Without the link, the first actual output is skipped; a run with just one output is never migrated.
- **Evidence:** running the migration helper on a synthetic directory containing only `run.0100.001` produced no Parquet file.
- **TODO:** identify any intentional initial-file exclusion by explicit name/type rather than list position. Share migration and runtime compaction logic, and test both with and without an initial link.

### 18. P2 — Environment loading points at a directory instead of the project dotenv file

- **Location:** `astra_web/utils.py:7–21`, `astra_web/auth/auth_schemes.py:5`.
- `load_dotenv('/')` points at the root directory, not the repository `.env`. Direct local Python startup therefore does not load the project file through this helper. Missing binary configuration produces paths such as `None/generator`. Data-path settings are also concatenated to the repository path, so conventional absolute-path overrides are not honored as absolute paths.
- **TODO:** load an explicit project dotenv file when appropriate, centralize and validate required settings, document path semantics, and use proper path handling. Distinguish the Compose interpolation name `ASTRA_API_KEY` from the runtime variable `API_KEY` in local setup instructions.

## Additional TODOs and maintenance gaps

- **Add automated regression coverage and CI.** `pyproject.toml:1–9` points pytest at `tests`, but no tests were collected. Start with authentication, path containment, compaction recovery, simulation construction, POST/GET agreement, subprocess failures, and numerical round trips.
- **Replace JSON string replacement with a deliberate namelist serializer.** `astra_web/decorators/decorators.py:9–14` contains the explicit repository TODO “use regex here.” Global comma/quote replacement also modifies string values, so regex alone is not a complete solution. Test quoting and escaping as well as indexed module keys against the actual ASTRA parser.
- **Restore or explicitly deprecate macroscopic statistics.** `astra_web/simulation/statistics.py:40–41` always returns an empty `macroscopic_states` list; the calculation is commented out despite remaining in the response schema.
- **Handle degenerate statistics explicitly.** `astra_web/simulation/statistics.py:24–33` converts particles outside the error handler, catches only two exception types, and falls back to a range of raw `z` values. Those values mix the absolute reference coordinate with relative particle offsets, as shown by the conversion logic in `particles.py:89`. Define behavior for all-lost, empty, zero-charge, and undersized slices, and report when statistics could not be calculated.
- **Make optional annotations match defaults.** Several scalar fields in generator and simulation schemas are annotated as non-nullable but default to `None`. For example, omitting `Solenoid.max_field_strength` succeeds while explicitly passing null fails. Choose and document consistent missing/null semantics.
- **Reject unknown nested settings consistently.** `SimulationInput` and `GeneratorInput` forbid extra fields, while module, run, and space-charge models generally ignore them. A typo can silently retain a default and change the experiment. Also document whether ASTRA field names, API aliases, or both are accepted.
- **Use a production startup command.** `start.sh:4` always enables `uvicorn --reload`, including the production Compose deployment. Separate development startup from production, and consider process signal handling and graceful shutdown.
- **Make builds reproducible.** Most Python dependencies are unpinned, the install command upgrades them, and `nginx:latest` plus mutable ASTRA download URLs are used. Lock a tested dependency set and record image/binary versions or digests. No vulnerability audit or clean image build was performed in this review.
- **Make maintenance utilities configurable.** The snapshot and macro-state scripts assume a relative `simulation` directory; `merge_macro_states.py:10` additionally fixes the filename to `run.macro_states.0000-0450.001.npy`. Add explicit input/output paths, useful per-run errors, and documented invocation.
- **Bound result-loading memory and concurrent jobs.** Entire Parquet files are loaded into Pandas and expanded into Python lists; statistics repeats this for every requested simulation. Assess final-snapshot filtering, pagination/selective result retrieval, and service resource limits before scaling to large distributions.
- **Update setup and API documentation.** `main.py:43` still says “Description to be done”; the two list handlers share a Python name; the run schema references a nonexistent `/generate` endpoint; the default distribution still names the locally deleted `example.ini`. Document required storage initialization, environment variables, request examples, output storage/migration, and errors. Ensure empty storage directories can be initialized on a fresh deployment.

## Validation and limits

- Read the application, schemas, scripts, requirements, Docker/Compose/nginx configuration, README, and changelog. No applicable `AGENTS.md` was found in the repository or checked ancestor locations.
- Parsed all 24 Python source files with `ast.parse`; imported the FastAPI application successfully.
- Ran isolated checks using the existing Python 3.12.3 virtual environment: FastAPI 0.109.2, Pydantic 2.6.0, Pandas 2.3.1, PyArrow 21.0.0, and openpmd-beamphysics 0.9.13.
- Used temporary directories and synthetic particles for filesystem/Parquet checks. Mocked recursive deletion and failing subprocesses. Verified the missing-key authentication case through the ASGI application. No ASTRA binary was launched and no existing simulation data was modified.
- `PYTHONDONTWRITEBYTECODE=1 venv/bin/python -m pytest --collect-only -p no:cacheprovider` exited with code 5: no tests collected, with a warning that the configured test directory was absent.
- Docker builds, live proxy behavior, MPI execution/cleanup, and numerical agreement with ASTRA were not exercised. These remain integration-validation tasks; this is not a complete security or scientific validation audit.

## Schema naming and defaults review — 2026-10-08

Scope: current generator and simulation Pydantic schemas, with emphasis on
`simulation/schemas/modules.py`, their input aliases, defaults, and ASTRA export.
This is an additional review, not an implementation change. Earlier findings above
describe the older tree; in particular, aperture-only construction and field-table
sample validation have since been added.

### Confirmed issues

1. **One duplicate input alias controls two independent output settings.**
   `simulation/schemas/io.py:46–55`: `High_res` and `RefS` both consume
   `high_accuracy`. Reproduced: `SimulationOutputSpecification(high_accuracy=False)`
   sets both to false. The generated schema also gives that single property the
   `RefS` description, obscuring its precision effect. Keep one alias per field;
   use a separate `generate_reference_output` for `RefS`. The converter currently
   compensates for this collision and must be updated with the schema.

2. **Native attribute names and misspelled aliases can silently select defaults.**
   `simulation/schemas/modules.py:8,40–80,100–142,162–192`, plus the run and
   space-charge models: `validation_alias` changes the accepted input key, but
   these models neither enable population by attribute name nor forbid extra
   keys. Reproduced: `Cavity(MaxE=58.1).MaxE == 130.0`,
   `Quadrupole(Q_K=5).Q_K == 10`, and
   `SimulationRunSpecifications(H_max=0.2).H_max == 0.001`.
   Require consistent rejection of unknown settings. Explicitly decide whether
   Python callers may also use ASTRA attribute names; if so, enable the matching
   Pydantic configuration and test inputs supplying both names. `Aperture` already
   forbids extra keys; the other nested models should be equally predictable.

3. **32 fields have defaults inconsistent with their annotations.**
   A field-by-field validation audit found non-nullable annotations with `None`
   defaults: 15 generator inputs; 2 cavity fields; 4 solenoid fields; 3 quadrupole
   fields; 4 run fields; 4 space-charge fields. Pydantic 2.6 does not validate these
   defaults by default. Reproduced: `Solenoid().MaxB` is `None`, but
   `Solenoid(max_field_strength=None)` raises a validation error. For settings
   intentionally omitted from ASTRA export, use `float | None = None` (or the
   appropriate optional type). Required geometry and data should be required
   instead. Make defaults valid before enabling `validate_default`.

4. **Default field-map modules export filenames without creating their files.**
   `simulation/schemas/modules.py:26–38,83–86,108–125,155–158`: `Cavity` and
   `Solenoid` allow no table, emit `File_Efield` / `File_Bfield`, and skip writing
   the table. Reproduced with an empty temporary directory: neither default module
   wrote any file. Require the table for the supported map-based module modes.
   Default quadrupoles likewise leave effective length and position unspecified;
   require these for the currently supported analytic geometry.

5. **Ordinary model serialization cannot round-trip API inputs.**
   `simulation/schemas/modules.py:9–14`: the custom serializer emits indexed ASTRA
   names, and `field_table` is excluded. Consequently `by_alias=True` does not
   produce a reusable request object. A cavity configured with strength 58.1 and
   a table loses both values when its dump is passed back to `model_validate`.
   Separate request serialization from ASTRA export, or provide an explicit,
   documented request-export method that preserves aliases and embedded tables.

6. **Several names imply the wrong physical meaning.**
   `run.py:92–103`: `start_time` / `end_time` should be `min_time_step` /
   `max_time_step`. `modules.py:46–50,127–131,188–192`: cavity and solenoid
   positions are map offsets, whereas quadrupole position is its centre.
   `modules.py:182–186`: `bore_radius` should describe fringe-field tapering;
   the manual relates the parameter to bore diameter. These interpretations were
   checked against the [ASTRA manual, sections 6.1 and 6.9–6.11](https://www.desy.de/~mpyflo/Astra_manual/Astra-Manual_V3.2.pdf).
   Correct documentation and introduce compatible aliases before removing old
   request names.

7. **Some defaults hide missing physical configuration.**
   `modules.py:40–42,68–70,176–178`: 1.3 GHz, 130 MV/m, and focusing strength 10
   are specific setup choices. Prefer required values or an explicitly selected
   machine preset. `run.py:49–65` also falls back to `example.ini`, which is absent
   in the checked working tree; require a registered particle-distribution ID.
   `run.py:110–114` forces cathode position zero, overriding ASTRA's automatic
   inference when it is omitted; consider an optional value instead.

8. **Traveling-wave cell counts need cross-field validation.**
   `modules.py:76–80` only enforces positivity. For a header with `n=1, m=3`,
   counts 1 and 2 currently pass, as does omission. ASTRA requires
   `cell_count * n / m` to be integral and documents an omitted `C_numb` default
   of 1. Require a valid count for TWS inputs or explicitly handle the effective
   default. The ordinary-cavity `higher_order` option is inapplicable to TWS and
   should be described accordingly. Source: [ASTRA manual, section 6.9](https://www.desy.de/~mpyflo/Astra_manual/Astra-Manual_V3.2.pdf).

9. **Validation is inconsistent across old and new models.**
   Apertures and field tables check finite numbers and related geometry; most
   older scalar models do not. Reproduced acceptance of `NaN` / infinity for
   strengths, `start_time=1, end_time=0`, a negative timeout, negative particle
   counts, reversed output limits, and negative distribution-checkpoint counts.
   Use finite numbers and appropriate bounds, plus validators for related
   settings. Preserve intentional sentinel values such as disabled beam scaling.
   Also review `SpaceCharge.N_min` (`space_charge.py:67–73`): it is currently an
   integer, although the manual specifies a real-valued average.

10. **The advertised run-number setting is not respected by output readers.**
    `run.py:44–48` exposes arbitrary `run_number`, while
    `simulation.py:86` and `utils.py:29` use `.001` filenames. Either propagate
    the selected number throughout output loading or constrain the API to the
    supported value until that implementation is completed.

### Default-value assessment

The comparisons below use the [ASTRA V3.2 manual](https://www.desy.de/~mpyflo/Astra_manual/Astra-Manual_V3.2.pdf),
not a verification of the installed executable. A different API default can be
intentional; it should be documented as a preset rather than presented as native
ASTRA behavior.

| Setting | Current API | Manual | Recommendation |
| --- | --- | --- | --- |
| Cavity / solenoid smoothing | 10 | 0 | Explicit processing choice; consider 0 for faithful imports. |
| Cavity higher order | true | false | Document the API's choice and its applicability. |
| `Q_Bore` | 0.035 m | 0.035 m | Keep the value; correct the public name. |
| `Nrad` | 32 | 10 | Document the resolution/cost choice. |
| `N_min` | 10 | 30 | Document the emission-stepping choice and correct the type. |
| Output `ZSTOP` | 1 m | 0.3 m | Prefer an explicit stop position or documented preset. |
| Output precision / output switches | true | false | Reasonable API convenience; document storage implications. |
| `H_min`, `H_max` | 0, 0.001 ns | Same | Keep values; fix aliases and validate their relationship. |
| `XYrms`, `Trms` | -1 | Same | Keep intentional no-rescaling sentinels. |

The converter currently fills omitted settings using API defaults. Therefore,
converting a sparse native deck can change smoothing, expansion order, grid
settings, or output behavior. Choose explicitly whether conversion preserves
native defaults or adopts an API preset, and test that choice.

### Naming consistency and observations that are not defects

- The existing convention of ASTRA names internally and descriptive request
  aliases is workable; it needs a consistent input/serialization policy.
- There are no repeated field declarations and no other input-alias collisions
  within the audited models. Reusing `frequency`, `phase`, `z_0`, or
  `max_field_strength` in different nested model types is not itself a collision.
- `max_field_strength` remains a valid name for the exposed cavity gradient.
  Keep its MV/m documentation; do not relabel this field as voltage.
- Prefer `effective_length` over `q_len`, `focusing_strength` over `q_focus`,
  `radial_grid_cells` over `grid_cell_count`, and a consistent lower-case pattern
  such as `grid_cells_x_3d` instead of `3D_x_grid_size`.
- `thread_num` actually controls MPI process count (`simulation.py:60–61`);
  `mpi_processes` would describe its implementation more accurately.
- Generator naming also mixes descriptive aliases with raw `Add`, `N_add`,
  `cor_px`, and `cor_py`. `sig_t` could become `rms_emission_time`, and
  `rms_dist_px` / `rms_dist_py` could describe momentum directly.
- `Aperture` has sensible zero offsets/rotations and conditional geometry
  validation. Its `radius` field is overloaded across geometry types; future
  typed variants could expose `radius`, `half_gap`, and `scraper_position`.
  `xz_rotation` / `yz_rotation` accurately describe planes rather than axes.
- Pydantic copies mutable list defaults in these models. An isolated check
  confirmed no sharing between two `Particles` instances. `default_factory`
  would improve consistency, but the existing lists are not a reproduced
  shared-state bug.
- Minor documentation errors: `Zphase` mentions `z_emit`, `Nyf` describes the x
  direction, generator `C_sig_x` / `C_sig_y` describe the longitudinal cutoff,
  and `sig_clock` repeats “RMS”. These should describe their actual fields.

Validation: inspected schema declarations; automatically checked input aliases,
duplicate declarations, and defaults against their annotations; reproduced the
listed validation and serialization behaviors under the repository's Pydantic
2.6.0 environment; used temporary files for missing-table checks. No native ASTRA
simulation was run, no application code was changed, and no existing run data
was modified.

### Implementation update — alias migration and null handling, 2026-10-08

The requested alias migration and null handling are now implemented:

- Canonical inputs are `min_time_step`, `max_time_step`, cavity/solenoid
  `z_offset`, and quadrupole `z_center`, `effective_length`, `focusing_strength`,
  and `fringe_taper_length`. The previous names remain accepted as legacy aliases;
  generated request schemas and the ASTRA converter use the canonical names.
- `RefS` now has the independent alias `generate_reference_output`.
  `high_accuracy` only controls `High_res`; the old coupling is intentionally
  removed. Existing clients that depended on that coupling must set both flags.
- Shared request validation accepts ASTRA attribute names, rejects unknown keys,
  validates defaults, and rejects conflicting values under multiple aliases.
- Optional `None` defaults now have nullable annotations. Null optional numeric
  settings are omitted from ASTRA export. Cavities and solenoids require field
  tables; quadrupoles require positive effective length and a centre position.
  Incomplete modules are rejected before simulation-directory creation.
- Converter and README examples were updated. Regression coverage includes alias
  compatibility, conflicts, independent output flags, nullable overrides,
  required module inputs, and ASTRA-file conversion round trips. The generated
  OpenAPI schema was checked for the new names and null/required declarations.
