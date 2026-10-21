"""Bound expensive jobs per API process without blocking the event loop."""
import asyncio
import os
from concurrent.futures import ThreadPoolExecutor
from threading import BoundedSemaphore

from fastapi import HTTPException


def positive_setting(name, default):
    value = int(os.getenv(name, default))
    if value < 1:
        raise ValueError(f"{name} must be positive")
    return value


MAX_MPI_PROCESSES = positive_setting("ASTRA_MAX_MPI_PROCESSES", "1")
_capacity = positive_setting("ASTRA_MAX_CONCURRENT_JOBS", "1")
_slots = BoundedSemaphore(_capacity)
_workers = ThreadPoolExecutor(max_workers=_capacity, thread_name_prefix="astra-job")


async def run_job(function, *args):
    if not _slots.acquire(blocking=False):
        raise HTTPException(503, "All job slots are busy; retry later.", headers={"Retry-After": "5"})

    try:
        future = _workers.submit(function, *args)
    except BaseException:
        _slots.release()
        raise
    # The concurrent future owns the slot even if its HTTP request is cancelled.
    future.add_done_callback(lambda _: _slots.release())
    return await asyncio.wrap_future(future)


def check_mpi_processes(simulation_input):
    if simulation_input.run_specs.thread_num > MAX_MPI_PROCESSES:
        raise HTTPException(422, f"run_specs.thread_num exceeds server limit ({MAX_MPI_PROCESSES}).")
