import os
from dotenv import load_dotenv
from datetime import datetime


def get_env_var(variable_name: str) -> str:
    if variable_name not in os.environ:
        load_dotenv("../")
        var = os.getenv(variable_name)
    else:
        var = os.environ[variable_name]

    return var


def default_filename(timestamp) -> str:
    data_path = os.path.abspath(os.path.join(__file__, "../../../data"))
    filename = timestamp

    return os.path.join(data_path, filename)


def output_filename(timestamp: str) -> str:
    return default_filename(timestamp) + ".out"


def particle_outputfile(timestamp: str) -> str:
    return default_filename(timestamp) + ".ini"


def outputfile_exists(timestamp) -> bool:
    return os.path.exists(particle_outputfile(timestamp))
