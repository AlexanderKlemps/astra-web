import pandas as pd
import numpy as np
from pmd_beamphysics import ParticleGroup
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

    def to_df(self):
        return pd.DataFrame(self.dict())

    def to_pmd(self, ref=None) -> ParticleGroup:
        """
        Helper function to transform the particle output from ASTRA to a ParticleGroup object for analysis.

        Parameters
        ----------
        :param particles: DataFrame
            A pandas DataFrame holding information on a particle distribution formatted as defined by ASTRA. Refer
            to the ASTRA manual for further information.
        :return: ParticleGroup
        """
        data = self.to_df()
        ref = ref if ref is not None else data.iloc[0]

        data['weight'] = np.abs(data.pop('macro_charge')) * 1e-9
        data.loc[1:, 'z'] = data.loc[1:, 'z'] + ref['z']
        data.loc[1:, 'pz'] = data.loc[1:, 'pz'] + ref['pz']
        data.loc[1:, 't_clock'] = (data.loc[1:, 't_clock'] + ref['t_clock']) * 1e-9
        data.loc[data['status'] == 1, 'status'] = 2
        data.loc[data['status'] == 5, 'status'] = 1

        data_dict = data.to_dict('list')
        data_dict['n_particles'] = data.size
        data_dict['species'] = 'electron'
        data_dict['t'] = ref['t_clock'] * 1e-9

        return ParticleGroup(data=data_dict)