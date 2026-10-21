"""Diagnostics for invalid API requests, without echoing submitted values."""

import json
import logging
from uuid import uuid4

from fastapi import Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse


# Inherit Uvicorn's console handler so diagnostics appear in Docker logs.
logger = logging.getLogger("uvicorn.error.validation")


async def request_validation_error_handler(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    request_id = uuid4().hex
    # Pydantic's input can contain an entire field table or request body. Its
    # ctx can contain exception objects; neither is needed to identify a field.
    details = [
        {key: error[key] for key in ("loc", "msg", "type")}
        for error in exc.errors()
    ]
    logger.warning(
        "Request validation failed: request_id=%s method=%s path=%s errors=%s",
        request_id,
        request.method,
        json.dumps(request.url.path),
        json.dumps(details),
    )
    return JSONResponse(
        status_code=422,
        content={"detail": details, "request_id": request_id},
        headers={"X-Request-ID": request_id},
    )
