#!/bin/bash

exec uvicorn astra_web.main:app --host 0.0.0.0 --port 8080 "$@"
