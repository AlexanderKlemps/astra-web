# ASTRA Web API
This repository contains an API wrapper for the well-known [ASTRA simulation code](https://www.desy.de/~mpyflo/) by
K. Floettmann (DESY Hamburg) based on the Python FastAPI package and Docker.

# Startup

## Local deployment in development environment 

Build the image and start container by execution of the following command

    docker compose stop && docker compose up -d --build

## Deployment in productive environment

In case you would like to deploy the API in a productive environment, say on a remote server, it is recommended to do
this via [Docker contexts](https://docs.docker.com/engine/context/working-with-contexts/).

Uncomment the COMPOSE_FILE environment variable in the .env file contained within this project an run

    docker context use [YOUR_REMOTE_CONTEXT]
    docker compose stop && docker compose up -d --build

# API documentation

In case you are running the API server locally, you will find the interactive API documentation under

    http://localhost:8000/docs

# Troubleshooting

### Problem: Rootless containers on the remote host quit once the user terminates the ssh session.
    
This is not an issue of Docker. Linux stops processes started by a normal user if loginctl is configured to not use 
lingering, to prevent normal users to keep long-running processes executing in the system.
In order to fix the problem, one can enable lingering by executing 

    loginctl enable-linger $UID

on the remote host.
Source: [Stackoverflow](https://stackoverflow.com/a/73312070)

# Cite this project

If you use this project in your scientific work and find it useful, you could use the following BibTeX entry to cite this project.

      @misc{astra-web,
        Author = {A. Klemps},
        Title = {ASTRA-Web},
        Year = {2024},
        publisher = {GitHub},
        journal = {https://github.com/AlexanderKlemps/astra-generator},
        version = {0.1}
      }
