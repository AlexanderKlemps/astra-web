import os
from dotenv import load_dotenv


def get_env_var(variable_name: str) -> str:
    if variable_name not in os.environ:
        load_dotenv("../")
        var = os.getenv(variable_name)
    else:
        var = os.environ[variable_name]

    return var


DATA_PATH = f"../../../{get_env_var('GENERATOR_DATA_PATH')}"


def default_filename(timestamp) -> str:
    data_path = os.path.abspath(os.path.join(__file__, DATA_PATH))
    filename = timestamp

    return os.path.join(data_path, filename)
