"""Shared validation policy for API input schemas."""

from collections.abc import Mapping
from typing import Any

from pydantic import AliasChoices, BaseModel, ConfigDict, model_validator


class RequestModel(BaseModel):
    model_config = ConfigDict(
        extra='forbid', populate_by_name=True, validate_default=True
    )

    @model_validator(mode='before')
    @classmethod
    def check_input_names(cls, data: Any) -> Any:
        """Accept renamed aliases without silently choosing conflicting values.

        The first AliasChoices entry is the public name. Equal duplicate inputs
        are collapsed before Pydantic's extra-field check. Never mutate callers.
        """
        if not isinstance(data, Mapping):
            return data
        result = dict(data)
        for name, field in cls.model_fields.items():
            alias = field.validation_alias
            names = alias.choices if isinstance(alias, AliasChoices) else [alias or name]
            names = list(dict.fromkeys([*names, name]))
            supplied = [key for key in names if isinstance(key, str) and key in result]
            if len(supplied) < 2:
                continue
            first = supplied[0]
            if any(result[key] != result[first] for key in supplied[1:]):
                raise ValueError(f'Conflicting values for {first}: {", ".join(supplied)}')
            for key in supplied[1:]:
                del result[key]
        return result
