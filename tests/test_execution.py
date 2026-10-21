import asyncio
from threading import Event

import pytest
from fastapi import HTTPException

from astra_web import execution, main


def test_running_job_keeps_health_responsive_and_rejects_overload(monkeypatch):
    from threading import BoundedSemaphore
    monkeypatch.setattr(execution, "_slots", BoundedSemaphore(1))
    started, finish = Event(), Event()

    def blocking_job():
        started.set()
        assert finish.wait(5)
        return "done"

    async def scenario():
        task = asyncio.create_task(execution.run_job(blocking_job))
        try:
            for _ in range(100):
                if started.is_set():
                    break
                await asyncio.sleep(.01)
            assert started.is_set()
            assert await asyncio.wait_for(main.health(), .5) == {"status": "ok"}
            with pytest.raises(HTTPException) as error:
                await execution.run_job(lambda: None)
            assert error.value.status_code == 503
            assert error.value.headers == {"Retry-After": "5"}
            task.cancel()
            with pytest.raises(asyncio.CancelledError):
                await task
            with pytest.raises(HTTPException):
                await execution.run_job(lambda: None)
        finally:
            finish.set()
        for _ in range(100):
            try:
                assert await execution.run_job(lambda: "available") == "available"
                break
            except HTTPException:
                await asyncio.sleep(.01)
        else:
            pytest.fail("Job slot was not released")

    asyncio.run(scenario())


def test_job_exception_releases_slot():
    def fail():
        raise ValueError("failed")

    async def scenario():
        with pytest.raises(ValueError, match="failed"):
            await execution.run_job(fail)
        assert await execution.run_job(lambda: 42) == 42

    asyncio.run(scenario())


def test_mpi_limit_rejects_before_start(monkeypatch):
    from astra_web.simulation.schemas.io import SimulationInput
    monkeypatch.setattr(execution, "MAX_MPI_PROCESSES", 1)
    request = SimulationInput(run_specs={"thread_num": 2})
    with pytest.raises(HTTPException) as error:
        asyncio.run(main.run_simulation(request))
    assert error.value.status_code == 422
