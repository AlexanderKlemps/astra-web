import math
import re
from pathlib import Path
from typing import Annotated, Self, Type, TypeVar

import pandas as pd
from pydantic import BaseModel, ConfigDict, Field, FiniteFloat, model_validator

T = TypeVar('T', bound='Parent')


class TravelingWaveHeader(BaseModel):
    """ASTRA TWS header; positions are local to the field map, in metres."""

    model_config = ConfigDict(extra='forbid')

    z1: FiniteFloat = Field(description='Start of the traveling-wave region in metres.')
    z2: FiniteFloat = Field(description='End of the traveling-wave region in metres.')
    n: int = Field(description='Phase-advance numerator; negative for backward waves.')
    m: int = Field(gt=0, description='Phase-advance denominator: phase per cell is 2*pi*n/m.')

    @model_validator(mode='after')
    def validate_header(self) -> Self:
        if self.z1 >= self.z2:
            raise ValueError('Traveling-wave boundaries must satisfy z1 < z2')
        if self.n == 0:
            raise ValueError('Traveling-wave phase-advance numerator n must be nonzero')
        return self


class FieldTable(BaseModel):
    z: list[FiniteFloat] = Field(
        min_length=2,
        description='Longitudinal positions along z-axis, in strictly increasing order.',
        json_schema_extra={'format': 'Unit: [m]'}
    )
    v: list[FiniteFloat] = Field(
        min_length=2,
        description='Field values at z positions in free units.',
        json_schema_extra={'format': 'Unit: free'}
    )
    traveling_wave: TravelingWaveHeader | None = Field(
        default=None,
        description='Optional z1, z2, n, m header for an ASTRA traveling-wave cavity map.'
    )

    @model_validator(mode='after')
    def validate_samples(self) -> Self:
        if len(self.z) != len(self.v):
            raise ValueError('Field-table z and v must have the same length')
        if any(right <= left for left, right in zip(self.z, self.z[1:])):
            raise ValueError('Field-table z positions must be strictly increasing')
        header = self.traveling_wave
        if header is not None and not self.z[0] <= header.z1 < header.z2 <= self.z[-1]:
            raise ValueError('Traveling-wave boundaries must lie within the sampled z range')
        return self

    @classmethod
    def from_csv(cls, file_name: str | Path) -> Self:
        """Read two-column samples with an optional four-number first record.

        Blank lines and !/# comments are ignored. Fortran D exponents and
        integer-valued header numbers such as 1.0 and 3.0 are accepted.
        """
        z, v = [], []
        header = None
        first_record = True
        with open(file_name, encoding='utf-8-sig') as source:
            for line_number, line in enumerate(source, 1):
                columns = re.split(r'[!#]', line, maxsplit=1)[0].split()
                if not columns:
                    continue
                is_header = first_record and len(columns) == 4
                if not is_header and len(columns) != 2:
                    raise ValueError(f'{file_name}:{line_number}: expected two sample columns; '
                                     'only the first record may contain a four-number TWS header')
                try:
                    values = [float(re.sub('[dD]', 'e', column)) for column in columns]
                except ValueError as exc:
                    raise ValueError(f'{file_name}:{line_number}: invalid field-map number') from exc
                if not all(math.isfinite(value) for value in values):
                    raise ValueError(f'{file_name}:{line_number}: field-map values must be finite')
                if is_header:
                    # Pydantic accepts integral floats but rejects fractional n/m.
                    header = TravelingWaveHeader(z1=values[0], z2=values[1], n=values[2], m=values[3])
                else:
                    z.append(values[0])
                    v.append(values[1])
                first_record = False
        return cls(z=z, v=v, traveling_wave=header)

    def to_csv(self, file_name: str | Path) -> None:
        """Write the optional TWS header followed by the ordinary z/value rows."""
        with open(file_name, 'w', encoding='utf-8') as output:
            header = self.traveling_wave
            if header is not None:
                output.write(f'{header.z1} {header.z2} {header.n} {header.m}\n')
            pd.DataFrame({'z': self.z, 'v': self.v}).to_csv(
                output, sep=' ', header=False, index=False
            )


class ApertureTable(BaseModel):
    """Circular aperture contour: local z in metres, radius in millimetres."""

    model_config = ConfigDict(extra='forbid')

    z: list[FiniteFloat] = Field(
        min_length=2,
        description='Local longitudinal positions in metres, in nondecreasing order.'
    )
    radius: list[Annotated[FiniteFloat, Field(ge=0)]] = Field(
        min_length=2,
        description='Aperture radii in millimetres at the corresponding z positions.'
    )

    @model_validator(mode='after')
    def validate_samples(self) -> Self:
        if len(self.z) != len(self.radius):
            raise ValueError('Aperture-table z and radius must have the same length')
        if any(right < left for left, right in zip(self.z, self.z[1:])):
            raise ValueError('Aperture-table z positions must be nondecreasing')
        if self.z[0] == self.z[-1]:
            raise ValueError('An aperture must have a positive longitudinal extent')
        return self

    @classmethod
    def from_csv(cls, file_name: str | Path) -> Self:
        """Read a two-column contour, allowing comments and Fortran D exponents."""
        z, radius = [], []
        with open(file_name, encoding='utf-8-sig') as source:
            for line_number, line in enumerate(source, 1):
                columns = re.split(r'[!#]', line, maxsplit=1)[0].split()
                if not columns:
                    continue
                if len(columns) != 2:
                    raise ValueError(f'{file_name}:{line_number}: expected two aperture columns (z, radius)')
                try:
                    values = [float(re.sub('[dD]', 'e', column)) for column in columns]
                except ValueError as exc:
                    raise ValueError(f'{file_name}:{line_number}: invalid aperture-table number') from exc
                if not all(math.isfinite(value) for value in values):
                    raise ValueError(f'{file_name}:{line_number}: aperture-table values must be finite')
                z.append(values[0])
                radius.append(values[1])
        return cls(z=z, radius=radius)

    def to_csv(self, file_name: str | Path) -> None:
        pd.DataFrame({'z': self.z, 'radius': self.radius}).to_csv(
            file_name, sep=' ', header=False, index=False
        )


class XYEmittanceTable(BaseModel):
    z: list[float] = Field(
        description='Longitudinal positions.',
        json_schema_extra={'format': 'Unit: [m]'}
    )
    t: list[float] = Field(
        description='Time points',
        json_schema_extra={'format': 'Unit: [ns]'}
    )
    mean: list[float] = Field(
        description='Average transverse position in x or y direction.',
        json_schema_extra={'format': 'Unit: [mm]'}
    )
    position_rms: list[float] = Field(
        description='RMS deviation in x or y direction.',
        json_schema_extra={'format': 'Unit: [mm]'}
    )
    angle_rms: list[float] = Field(
        description='RMS inclination angle deviation in x or y direction.',
        json_schema_extra={'format': 'Unit: [mrad]'}
    )
    emittance:  list[float] = Field(
        description='Normed emittance in x or y direction.',
        json_schema_extra={'format': 'Unit: [pi*mrad*mm]'}
    )
    correlation: list[float] = Field(
        description='Correlation of position coordinates and momenta in x or y direction.',
        json_schema_extra={'format': 'Unit: [mrad]'}
    )

    @classmethod
    def from_csv(cls: Type[T], filename: str) -> T:
        df = pd.read_csv(filename, names=list(cls.model_fields.keys()), sep=r"\s+")
        return cls(**df.to_dict("list"))


class ZEmittanceTable(BaseModel):
    z: list[float] = Field(
        description='Longitudinal positions.',
        json_schema_extra={'format': 'Unit: [m]'}
    )
    t: list[float] = Field(
        description='Time points',
        json_schema_extra={'format': 'Unit: [ns]'}
    )
    E_kin: list[float] = Field(
        description='Average transverse position in x or y direction.',
        json_schema_extra={'format': 'Unit: [MeV]'}
    )
    position_rms: list[float] = Field(
        description='RMS deviation in x or y direction.',
        json_schema_extra={'format': 'Unit: [mm]'}
    )
    delta_E_rms: list[float] = Field(
        description='RMS inclination angle deviation in x or y direction.',
        json_schema_extra={'format': 'Unit: [keV]'}
    )
    emittance: list[float] = Field(
        description='Normed emittance in x or y direction.',
        json_schema_extra={'format': 'Unit: [pi*keV*mm]'}
    )
    correlation: list[float] = Field(
        description='Correlation of position coordinates and mean energy in x or y direction.',
        json_schema_extra={'format': 'Unit: [keV]'}
    )

    @classmethod
    def from_csv(cls: Type[T], filename: str) -> T:
        df = pd.read_csv(filename, names=list(cls.model_fields.keys()), sep=r"\s+")
        return cls(**df.to_dict("list"))