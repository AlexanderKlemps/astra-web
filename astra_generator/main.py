import os
from fastapi import FastAPI
from fastapi import FastAPI, Body, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from .generator.schemas import Input, Particle
from .generator.generator import write_input_file, process_generator_input, read_output_file

API_KEYS = [os.environ["API_KEY"]]

# API key authorization taken from here 
# https://testdriven.io/tips/6840e037-4b8f-4354-a9af-6863fb1c69eb/
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")  # use token authentication


def api_key_auth(api_key: str = Depends(oauth2_scheme)):
    if api_key not in API_KEYS:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Forbidden"
        )


app = FastAPI()


@app.post("/generate")  # dependencies=[Depends(api_key_auth)])
async def generate(generator_input: Input) -> list[Particle]:
    write_input_file(generator_input)
    process_generator_input(generator_input)
    process_output = read_output_file(generator_input.creation_time())

    return process_output
