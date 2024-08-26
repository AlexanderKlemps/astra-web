import pandas as pd
import numpy as np
from typing import Type, TypeVar
from pydantic import BaseModel, Field

T = TypeVar('T', bound='Parent')


class Particles(BaseModel):
    x: list[float] = Field(
        default=[],
        description='List of particle x values.',
        json_schema_extra={'format': 'Unit: [m]'}
    )
    y: list[float] = Field(
        default=[],
        description='List of particle y values',
        json_schema_extra={'format': 'Unit: [m]'}
    )
    z: list[float] = Field(
        default=[],
        description='List of particle z values.',
        json_schema_extra={'format': 'Unit: [m]'}
    )
    px: list[float] = Field(
        default=[],
        description='List of particle px values.',
        json_schema_extra={'format': 'Unit: [eV/c]'}
    )
    py: list[float] = Field(
        default=[],
        description='List of particle py values.',
        json_schema_extra={'format': 'Unit: [eV/c]'}
    )
    pz: list[float] = Field(
        default=[],
        description='List of particle pz values.',
        json_schema_extra={'format': 'Unit: [eV/c]'}
    )
    t_clock: list[float] | None = []
    macro_charge: list[float] = Field(
        default=[],
        description='List of particle macro charges.',
        json_schema_extra={'format': 'Unit: [nC]'}
    )
    species: list[int] | None = []
    status: list[int] | None = []

    @property
    def active_particles(self):
        return np.array(self.status) >= 0

    def to_csv(self, filename) -> None:
        pd.DataFrame(dict(self)).to_csv(filename, sep=" ", header=False, index=False)

    @classmethod
    def from_csv(cls: Type[T], filename: str) -> T:
        df = pd.read_csv(filename, names=list(cls.model_fields.keys()), sep=r"\s+")
        return cls(**df.to_dict("list"))