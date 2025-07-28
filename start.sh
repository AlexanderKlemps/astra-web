#!/bin/bash

source /opt/intel/oneapi/setvars.sh
uvicorn astra_web.main:app --host 0.0.0.0 --port 8000 --reload