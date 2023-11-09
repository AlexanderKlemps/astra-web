import os
from fastapi import FastAPI, Depends, HTTPException, status, APIRouter
from fastapi.security import OAuth2PasswordBearer
from .generator.schemas import Input, Output
from .generator.generator import write_input_file, process_generator_input, read_output_file


API_KEYS = [os.getenv("API_KEY")]

# API key authorization taken from here 
# https://testdriven.io/tips/6840e037-4b8f-4354-a9af-6863fb1c69eb/
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")  # use token authentication


def api_key_auth(api_key: str = Depends(oauth2_scheme)):
    if api_key not in API_KEYS:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Forbidden"
        )


app = FastAPI(root_path=os.getenv("ROOT_PATH", "/"))

@app.post("/generate")  # dependencies=[Depends(api_key_auth)])
async def generate(generator_input: Input) -> Output:
    write_input_file(generator_input)
    process_generator_input(generator_input)
    process_output = read_output_file(generator_input)

    return process_output