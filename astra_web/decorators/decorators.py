import pydantic


def ini_exportable(cls):
    # internal method for formatting the JSON dump
    # better not overwrite unless you know what you do
    def _to_ini(self: pydantic.BaseModel, indent=4) -> str:
        # replace key value delimiters ':', remove key double quotes, remove leading and trailing curly brackets
        # TODO: use regex here
        return (self.model_dump_json(indent=indent, exclude_none=True, by_alias=True)
                .replace("\": ", " = ")
                .replace(",", "")
                .replace("  \"", "  ")
                .replace("\"", "'"))[1:-1]

    # Main 'to_ini' function to be used calling internal _to_ini
    def to_ini(self: pydantic.BaseModel) -> str:
        return self._to_ini()

    setattr(cls, '_to_ini', _to_ini)
    if not hasattr(cls, 'to_ini'):
        setattr(cls, 'to_ini', to_ini)

    return cls
