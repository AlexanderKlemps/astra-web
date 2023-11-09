# Set Python version, download image
ARG PYTHON_VERSION

FROM python:$PYTHON_VERSION as build_api

WORKDIR /app

# Copy over python requirements and instantiate
COPY ../requirements/requirements.txt /app/requirements.txt
RUN python3 -m pip install --upgrade pip && pip install --no-cache-dir --upgrade -r requirements.txt

# Copy over rest of directory
COPY .. /app

# Download most recent ASTRA generator binary from sources
ARG ASTRA_GENERATOR_BINARY_PATH
ENV ASTRA_GENERATOR_BINARY_PATH=${ASTRA_GENERATOR_BINARY_PATH}

RUN wget https://www.desy.de/~mpyflo/Astra_for_64_Bit_Linux/generator  \
    && chmod 777 generator  \
    && mv generator $ASTRA_GENERATOR_BINARY_PATH

# Run FastAPI server
ARG SERVER_ROOT_PATH
CMD ["uvicorn", "astra_generator.main:app", "--host", "0.0.0.0", "--port", "8000"]