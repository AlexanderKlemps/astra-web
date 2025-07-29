# Set Python version, download image
FROM alexanderklemps/astra-web:astra-09-24

WORKDIR /app

# Copy over python requirements and instantiate
COPY ../requirements/requirements.txt /app/requirements.txt
RUN python3 -m pip install --upgrade pip && pip install --upgrade -r requirements.txt

# Copy over rest of directory
COPY .. /app
RUN chmod 777 start.sh

# Set api key env variable
ARG API_KEY
ENV API_KEY=${API_KEY}
ARG BINARY_PATH
ENV ASTRA_BINARY_PATH=${BINARY_PATH}

# Run FastAPI server
ENTRYPOINT ["/bin/bash", "-c", "./start.sh"]