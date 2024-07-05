# Set Python version, download image
FROM alexanderklemps/astra-web:openmpi

WORKDIR /app

# Copy over python requirements and instantiate
COPY ../requirements/requirements.txt /app/requirements.txt
RUN python3 -m pip install --upgrade pip && pip install --no-cache-dir --upgrade -r requirements.txt

# Copy over rest of directory
COPY .. /app

# Set api key env variable
ARG API_KEY
ENV API_KEY=${API_KEY}
ARG BINARY_PATH
ENV ASTRA_BINARY_PATH=${BINARY_PATH}

# Download most recent ASTRA binaries from sources
RUN wget https://www.desy.de/~mpyflo/Astra_for_64_Bit_Linux/generator  \
    && chmod 777 generator && mv generator $ASTRA_BINARY_PATH/generator \
    && wget https://www.desy.de/~mpyflo/Astra_for_64_Bit_Linux/Astra; fi \
    && chmod 777 Astra  \ mv Astra $ASTRA_BINARY_PATH/astra \
    && wget https://www.desy.de/~mpyflo/Parallel_Astra_for_Linux/Astra; \
    && chmod 777 Astra  && mv Astra $ASTRA_BINARY_PATH/parallel_astra \

# Run FastAPI server
ENTRYPOINT ["uvicorn", "astra_web.main:app", "--host", "0.0.0.0", "--port", "8000"]