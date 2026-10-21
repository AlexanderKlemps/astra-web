#!/usr/bin/env python3
"""Convert an ASTRA namelist and its field maps into an ASTRA Web API request.

Usage: python bin/parse_astra_input.py path/to/run.in [-o simulation_in.json]
Only the ASTRA features represented by the repository's request schemas are
supported. Conversion does not create a simulation or contact the API.
"""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
import re
import sys
from typing import NamedTuple

# Allow invocation from any working directory without installing the project.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from pydantic import AliasChoices, BaseModel, ValidationError

from astra_web.simulation.schemas.io import SimulationOutputSpecification
from astra_web.simulation.schemas.modules import Aperture, Cavity, Quadrupole, Solenoid
from astra_web.simulation.schemas.run import SimulationRunSpecifications
from astra_web.simulation.schemas.space_charge import SpaceCharge
from astra_web.simulation.schemas.tables import ApertureTable, FieldTable


class ConversionError(ValueError):
    """The input cannot be represented faithfully by the API request schema."""


class Token(NamedTuple):
    kind: str
    text: str
    line: int


Scalar = str | int | float | bool
Index = int | tuple[int, int] | None
Section = dict[tuple[str, Index], Scalar]

TOKEN = re.compile(
    r"(?P<space>[\s]+)|(?P<comment>![^\n]*)"
    r"|(?P<string>'(?:[^']|'')*'|\"(?:[^\"]|\"\")*\")"
    r"|(?P<boolean>\.(?:true|false|t|f)\.)"
    r"|(?P<number>[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[ed][+-]?\d+)?)"
    r"|(?P<name>[a-z_][a-z_0-9]*)"
    r"|(?P<symbol>[&$()/=,])",
    re.IGNORECASE,
)


def _tokens(text: str) -> list[Token]:
    tokens = []
    pos, line = 0, 1
    index_depth = 0
    while pos < len(text):
        match = TOKEN.match(text, pos)
        if match is None:
            raise ConversionError(f"Line {line}: unsupported syntax near {text[pos:pos + 30]!r}")
        kind, value = match.lastgroup, match.group()
        # Commas separate assignments, but inside indices they must be preserved.
        if value == "(":
            index_depth += 1
        elif value == ")":
            index_depth -= 1
        if kind not in {"space", "comment"} and not (value == "," and index_depth == 0):
            tokens.append(Token(kind, value, line))
        line += value.count("\n")
        pos = match.end()
    return tokens


def _scalar(token: Token) -> Scalar:
    value = token.text
    if token.kind == "string":
        return value[1:-1].replace(value[0] * 2, value[0])
    if token.kind in {"boolean", "name"}:
        logical = value.lower().strip(".")
        if logical in {"true", "t", "false", "f"}:
            return logical in {"true", "t"}
    if token.kind == "number":
        if re.fullmatch(r"[+-]?\d+", value):
            return int(value)
        number = float(re.sub("[dD]", "e", value))
        if math.isfinite(number):
            return number
    raise ConversionError(f"Line {token.line}: expected a finite number, boolean, or quoted string; got {value!r}")


def parse_namelists(text: str) -> dict[str, Section]:
    """Read scalar assignments, positive module indices, and CAVITY.Phi(0).

    Names are case-insensitive. Supports ! comments, commas, Fortran D/E
    exponents, quoted strings with doubled quotes, and / or &END terminators.
    Two indices are supported for APERTURE.Ap_GR only. Array slices, repeat
    counts, and implicit array assignments are rejected.
    """
    tokens = _tokens(text)
    sections: dict[str, Section] = {}
    pos = 0

    def take(kind: str | None = None, value: str | None = None) -> Token:
        nonlocal pos
        if pos == len(tokens):
            raise ConversionError("Unexpected end of input (missing value or namelist terminator)")
        token = tokens[pos]
        if (kind and token.kind != kind) or (value and token.text.lower() != value):
            raise ConversionError(f"Line {token.line}: expected {value or kind}, got {token.text!r}")
        pos += 1
        return token

    while pos < len(tokens):
        marker = take("symbol")
        if marker.text not in {"&", "$"}:
            raise ConversionError(f"Line {marker.line}: expected a namelist beginning with &")
        name = take("name").text.lower()
        if name in sections:
            raise ConversionError(f"Duplicate namelist &{name.upper()}")
        values: Section = {}
        while True:
            if pos == len(tokens):
                raise ConversionError(f"Unterminated namelist &{name.upper()}")
            if tokens[pos].text == "/":
                take(value="/")
                break
            if tokens[pos].text in {"&", "$"}:
                take("symbol")
                take("name", "end")
                break
            key = take("name").text.lower()
            index = None
            if pos < len(tokens) and tokens[pos].text == "(":
                take(value="(")
                index_token = take("number")
                if not re.fullmatch(r"\+?\d+", index_token.text) or int(index_token.text) < (0 if name == "cavity" and key == "phi" else 1):
                    raise ConversionError(f"Line {index_token.line}: module index must be a positive integer")
                index = int(index_token.text)
                if pos < len(tokens) and tokens[pos].text == ",":
                    if name != "aperture" or key != "ap_gr":
                        raise ConversionError("Only &APERTURE.Ap_GR supports two indices")
                    take(value=",")
                    radius_index = take("number")
                    if not re.fullmatch(r"\+?\d+", radius_index.text) or int(radius_index.text) < 1:
                        raise ConversionError(f"Line {radius_index.line}: radius index must be a positive integer")
                    index = (index, int(radius_index.text))
                take(value=")")
            take(value="=")
            value = _scalar(take())
            if (key, index) in values:
                raise ConversionError(f"Duplicate assignment {key} in &{name.upper()}")
            values[key, index] = value
        sections[name] = values
    return sections


def _scalars(section: Section, name: str) -> dict[str, Scalar]:
    if any(index is not None for _, index in section):
        raise ConversionError(f"&{name}: indexed settings are not supported here")
    return {key: value for (key, _), value in section.items()}


def _api_settings(values: dict[str, Scalar], model: type[BaseModel], section: str) -> dict:
    # The API accepts validation aliases, not the names produced by model_dump.
    fields = {name.lower(): (name, field) for name, field in model.model_fields.items() if not field.exclude}
    result = {}
    for key, value in values.items():
        if key not in fields:
            raise ConversionError(f"&{section}: {key} is not supported by the REST API")
        name, field = fields[key]
        alias = field.validation_alias or name
        if isinstance(alias, AliasChoices):
            alias = alias.choices[0]
        if alias in result and result[alias] != value:
            raise ConversionError(f"&{section}: conflicting settings map to API field {alias!r}")
        result[alias] = value
    return result


def _boolean(value: Scalar, name: str) -> bool:
    if not isinstance(value, bool):
        raise ConversionError(f"{name} must be a logical value")
    return value


def read_field_table(path: Path) -> dict:
    """Return API field-table data, preserving any traveling-wave header."""
    try:
        return FieldTable.from_csv(path).model_dump(exclude_none=True)
    except ValueError as exc:
        raise ConversionError(f'{path}: {exc}') from exc


def _modules(section: Section, name: str, model: type[BaseModel], flag: str,
             field_key: str | None, source_dir: Path, field_map_dir: Path | None) -> list[dict]:
    values = dict(section)
    enabled = _boolean(values.pop((flag, None), bool(values)), f"&{name}.{flag}")
    if not enabled:
        return []
    indexed: dict[int, dict[str, Scalar]] = {}
    for (key, index), value in values.items():
        if index is None:
            raise ConversionError(f"&{name}: {key} requires an explicit module index")
        indexed.setdefault(index, {})[key] = value
    if not indexed:
        raise ConversionError(f"&{name}: enabled but no module settings were supplied")
    modules = []
    for index, settings in sorted(indexed.items()):
        filename = settings.pop(field_key, None) if field_key else None
        module = _api_settings(settings, model, name)
        if field_key:
            if not isinstance(filename, str) or not filename:
                raise ConversionError(f"&{name}: {field_key}({index}) must name a field map")
            path = Path(filename)
            if field_map_dir is not None:
                # Explicit relocation also supports paths recorded inside a container.
                path = field_map_dir / path.name
            elif not path.is_absolute():
                path = source_dir / path
            module["field_table"] = read_field_table(path)
        model.model_validate(module)
        modules.append(module)
    return modules


def _apertures(section: Section, source_dir: Path, field_map_dir: Path | None) -> list[dict]:
    values = dict(section)
    enabled = _boolean(values.pop(("lapert", None), bool(values)), "&APERTURE.LApert")
    if not enabled:
        return []
    indexed: dict[int, dict[str, Scalar]] = {}
    grids: dict[int, dict[int, Scalar]] = {}
    for (key, index), value in values.items():
        if key == "ap_gr":
            if not isinstance(index, tuple):
                raise ConversionError("&APERTURE: Ap_GR requires aperture and radius indices")
            aperture_index, radius_index = index
            if radius_index > 40:
                raise ConversionError("&APERTURE: Ap_GR supports at most 40 radii (20 rings)")
            grids.setdefault(aperture_index, {})[radius_index] = value
            indexed.setdefault(aperture_index, {})
        else:
            if not isinstance(index, int):
                raise ConversionError(f"&APERTURE: {key} requires an explicit aperture index")
            indexed.setdefault(index, {})[key] = value
    if not indexed:
        raise ConversionError("&APERTURE: enabled but no aperture settings were supplied")

    keywords = {name.lower(): name for name in ("RAD", "Cir", "Scr_X", "Scr_Y", "Col_X", "Col_Y")}
    apertures = []
    for index, settings in sorted(indexed.items()):
        filename = settings.pop("file_aperture", None)
        if not isinstance(filename, str) or not filename:
            raise ConversionError(f"&APERTURE: File_Aperture({index}) must name a table or geometry keyword")
        aperture = _api_settings(settings, Aperture, "APERTURE")
        if filename.lower() in keywords:
            aperture["type"] = keywords[filename.lower()]
        else:
            aperture["type"] = "table"
            path = Path(filename)
            if field_map_dir is not None:
                path = field_map_dir / path.name
            elif not path.is_absolute():
                path = source_dir / path
            try:
                aperture["aperture_table"] = ApertureTable.from_csv(path).model_dump()
            except ValueError as exc:
                raise ConversionError(f'{path}: {exc}') from exc
        if index in grids:
            radii = grids[index]
            if sorted(radii) != list(range(1, len(radii) + 1)):
                raise ConversionError(f"&APERTURE: Ap_GR({index},j) radius indices must be consecutive from 1")
            aperture["grid_radii"] = [radii[j] for j in sorted(radii)]
        Aperture.model_validate(aperture)
        apertures.append(aperture)
    return apertures


def convert_input(input_path: Path, *, field_map_dir: Path | None = None,
                  particle_id: str | None = None) -> dict:
    """Return a JSON-ready request without SimulationInput's filesystem side effects."""
    sections = parse_namelists(input_path.read_text(encoding="utf-8-sig"))
    supported = {"newrun", "output", "charge", "cavity", "solenoid", "quadrupole", "aperture"}
    unknown = sections.keys() - supported
    if unknown:
        raise ConversionError(f"Namelists not supported by the REST API: {', '.join(sorted(unknown))}")
    if "newrun" not in sections:
        raise ConversionError("Missing &NEWRUN namelist")

    run = _scalars(sections["newrun"], "NEWRUN")
    run.pop("head", None)  # The API regenerates this descriptive heading.
    distribution = run.pop("distribution", None)
    if particle_id is None:
        if not isinstance(distribution, str) or not distribution:
            raise ConversionError("Distribution must name an .ini file, or supply --particle-id")
        path = Path(distribution)
        if path.suffix != ".ini":
            raise ConversionError("The API requires an .ini distribution; register it and use --particle-id")
        particle_id = path.stem
    if not particle_id or particle_id in {".", ".."} or any(c in particle_id for c in "/\\"):
        raise ConversionError("The particle ID must be a filename without a directory")
    run_specs = _api_settings(run, SimulationRunSpecifications, "NEWRUN")
    if "global_rf_phase_shift" in run_specs:
        raise ConversionError("Global RF phase belongs in &CAVITY as Phi(0), not &NEWRUN")
    cavity_settings = sections.get("cavity", {})
    if ("phi", 0) in cavity_settings:
        run_specs["global_rf_phase_shift"] = cavity_settings.pop(("phi", 0))
    run_specs["particle_file_name"] = particle_id
    SimulationRunSpecifications.model_validate(run_specs)

    output = _scalars(sections.get("output", {}), "OUTPUT")
    for key in ("high_res", "refs"):
        if key in output:
            _boolean(output[key], key)
    output_specs = _api_settings(output, SimulationOutputSpecification, "OUTPUT")
    SimulationOutputSpecification.model_validate(output_specs)

    charge = _scalars(sections.get("charge", {}), "CHARGE")
    transition = charge.pop("l2d_3d", None)
    if transition is not None and _boolean(transition, "L2D_3D") != ("z_trans" in charge):
        raise ConversionError("L2D_3D conflicts with z_trans; the API derives this flag from z_trans")
    space_charge = _api_settings(charge, SpaceCharge, "CHARGE")
    SpaceCharge.model_validate(space_charge)

    result = {"run_specs": run_specs, "output_specs": output_specs, "space_charge": space_charge}
    for name, target, model, flag, field_key in [
        ("cavity", "cavities", Cavity, "lefield", "file_efield"),
        ("solenoid", "solenoids", Solenoid, "lbfield", "file_bfield"),
        ("quadrupole", "quadrupoles", Quadrupole, "lquad", None),
    ]:
        result[target] = _modules(sections.get(name, {}), name.upper(), model, flag,
                                  field_key, input_path.parent, field_map_dir)
    result["apertures"] = _apertures(sections.get("aperture", {}), input_path.parent, field_map_dir)
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("input", type=Path, help="ASTRA input file, e.g. run.in")
    parser.add_argument("-o", "--output", type=Path, help="Output JSON (default: simulation_in.json beside the input)")
    parser.add_argument("--field-map-dir", type=Path, help="Read all referenced field and aperture tables from this directory by basename")
    parser.add_argument("--particle-id", help="Override the particle distribution ID registered with the API")
    args = parser.parse_args(argv)
    output = args.output or args.input.with_name("simulation_in.json")
    try:
        if output.resolve() == args.input.resolve():
            raise ConversionError("The output path must differ from the ASTRA input path")
        result = convert_input(args.input, field_map_dir=args.field_map_dir, particle_id=args.particle_id)
        encoded = json.dumps(result, indent=2, allow_nan=False) + "\n"
        output.write_text(encoded, encoding="utf-8")
    except (ConversionError, ValidationError, OSError, UnicodeError) as exc:
        parser.exit(1, f"error: {exc}\n")
    print(f"Wrote {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
