# Set Python version, download image
ARG PYTHON_VERSION
FROM python:$PYTHON_VERSION

WORKDIR /app

# Install apt dependencies
RUN apt update && apt install vim -y

# Copy over python requirements and instantiate
COPY ../requirements/requirements.txt /app/requirements.txt
RUN python3 -m pip install --upgrade pip && pip install --no-cache-dir --upgrade -r requirements.txt

# Copy over rest of directory
COPY .. /app

# Set api key env variable
ARG API_KEY
ENV API_KEY=${API_KEY}

ARG BINARY_PATH
ENV ASTRA_GENERATOR_BINARY_PATH=${BINARY_PATH}/generator
ARG BINARY_PATH
ENV ASTRA_SIMULATION_BINARY_PATH=${BINARY_PATH}/astra
ARG ENABLE_CONCURRENCY

# Download most recent ASTRA binaries from sources
RUN wget https://www.desy.de/~mpyflo/Astra_for_64_Bit_Linux/generator  \
    && chmod 777 generator  \
    && mv generator $ASTRA_GENERATOR_BINARY_PATH \
    && wget https://www.desy.de/~mpyflo/Astra_for_64_Bit_Linux/Astra \
    && chmod 777 Astra  \
    && mv Astra $ASTRA_SIMULATION_BINARY_PATH

# Run FastAPI server
ENTRYPOINT ["uvicorn", "astra_generator.main:app", "--host", "0.0.0.0", "--port", "8000"]