import pandas as pd
from pydantic import BaseModel, Field
from typing import Type, TypeVar

T = TypeVar('T', bound='Parent')


class FieldTable(BaseModel):
    z: list[float] = Field(
        description='Longitudinal positions along z-axis.',
        json_schema_extra={'format': 'Unit: [m]'}
    )
    v: list[float] = Field(
        description='Field values at z positions in free units.',
        json_schema_extra={'format': 'Unit: free'}
    )

    def to_csv(self, file_name) -> None:
        pd.DataFrame({'z': self.z, "v": self.v}).to_csv(file_name, sep=" ", header=False, index=False)


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