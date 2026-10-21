import asyncio
import json
import logging

import pytest
from fastapi import Depends

from astra_web import main
from astra_web.auth import auth_schemes
from astra_web.simulation.schemas import io as simulation_io


@pytest.fixture(autouse=True)
def isolate_requests(tmp_path, monkeypatch):
    monkeypatch.setattr(simulation_io, "SIMULATION_DATA_PATH", str(tmp_path))
    monkeypatch.setattr(auth_schemes, "API_KEYS", ["test-api-key"])
    monkeypatch.setattr(main, "process_simulation_input", lambda _: "simulation stub")

    # Exercise the actual authentication decision without making these response
    # tests depend on worker-thread scheduling in the test environment.
    async def authenticate(api_key: str = Depends(auth_schemes.auth_scheme)):
        return auth_schemes.api_key_auth(api_key)

    monkeypatch.setitem(main.app.dependency_overrides, auth_schemes.api_key_auth, authenticate)


def put_simulation(payload, *, content_type="application/json", api_key="test-api-key"):
    """Exercise the ASGI app without an additional HTTP-client dependency."""
    body = payload if isinstance(payload, bytes) else json.dumps(payload).encode()
    messages = []

    async def receive():
        return {"type": "http.request", "body": body, "more_body": False}

    async def send(message):
        messages.append(message)

    scope = {
        "type": "http", "asgi": {"version": "3.0"}, "http_version": "1.1",
        "method": "PUT", "scheme": "http", "path": "/simulations",
        "raw_path": b"/simulations", "root_path": "",
        "query_string": b"token=private-query-value",
        "headers": [(b"content-type", content_type.encode()),
                    (b"x-api-key", api_key.encode()),
                    (b"cookie", b"session=private-cookie-value")],
        "client": ("127.0.0.1", 12345), "server": ("testserver", 80),
    }
    async def request():
        await asyncio.wait_for(main.app(scope, receive, send), timeout=5)

    asyncio.run(request())
    start = next(m for m in messages if m["type"] == "http.response.start")
    data = json.loads(b"".join(m.get("body", b"") for m in messages
                              if m["type"] == "http.response.body"))
    return start["status"], dict(start["headers"]), data


@pytest.mark.parametrize("payload, location, error_type", [
    ({"cavities": [{}]}, ["body", "cavities", 0, "field_table"], "missing"),
    ({"cavities": [{"field_table": {"z": [0, 1], "v": [0, 1]},
                    "max_field_strength": "private-invalid-value"}]},
     ["body", "cavities", 0, "max_field_strength"], "float_parsing"),
    ({"output_specs": {"unknown_setting": "private-invalid-value"}},
     ["body", "output_specs", "unknown_setting"], "extra_forbidden"),
    ({"cavities": [{"field_table": {"z": [0, 1, 2], "v": [0, 1]}}]},
     ["body", "cavities", 0, "field_table"], "value_error"),
    ({"cavities": [{"field_table": {
        "z": [0, 1], "v": [0, 1],
        "traveling_wave": {"z1": 0.1, "z2": 0.9, "n": 1.5, "m": 3.0},
    }}]}, ["body", "cavities", 0, "field_table", "traveling_wave", "n"], "int_from_float"),
])
def test_invalid_request_identifies_field_in_response_and_logs(
    payload, location, error_type, caplog, tmp_path
):
    caplog.set_level(logging.WARNING, logger="uvicorn.error.validation")
    status, headers, data = put_simulation(payload)

    assert status == 422
    error = next(e for e in data["detail"] if e["loc"] == location)
    assert error["type"] == error_type
    assert error["msg"]
    assert set(error) == {"loc", "msg", "type"}
    assert headers[b"x-request-id"].decode() == data["request_id"]
    assert data["request_id"] in caplog.text
    assert json.dumps(location) in caplog.text
    assert "method=PUT" in caplog.text
    assert 'path="/simulations"' in caplog.text
    assert list(tmp_path.iterdir()) == []
    for secret in ("private-invalid-value", "private-query-value",
                   "private-cookie-value", "test-api-key"):
        assert secret not in caplog.text
        assert secret not in json.dumps(data)


def test_malformed_json_returns_parse_location(caplog):
    status, _, data = put_simulation(b'{"cavities":')
    assert status == 422
    assert data["detail"][0]["type"] == "json_invalid"
    assert data["detail"][0]["loc"][0] == "body"
    assert "json_invalid" in caplog.text


def test_non_json_bytes_do_not_break_error_serialization():
    status, _, data = put_simulation(b"\xffprivate-body", content_type="application/octet-stream")
    assert status == 422
    assert data["detail"][0]["loc"] == ["body"]
    assert "input" not in data["detail"][0]


def test_authentication_errors_keep_their_status_and_response(caplog):
    status, headers, data = put_simulation({"cavities": [{}]}, api_key="invalid-key")
    assert status == 401
    assert data == {"detail": "Forbidden"}
    assert b"x-request-id" not in headers
    assert "Request validation failed" not in caplog.text


def test_valid_request_is_not_logged_as_a_validation_failure(caplog):
    status, _, data = put_simulation({})
    assert status == 200
    assert data["output"] == "simulation stub"
    assert "Request validation failed" not in caplog.text


def test_reference_particle_check_request_is_exported(tmp_path):
    status, _, data = put_simulation({"run_specs": {"check_reference_particle": False}})
    assert status == 200, data
    run_file = next(tmp_path.glob("*/run.in"))
    assert "check_ref_part = false" in run_file.read_text()


@pytest.mark.parametrize("n, m", [(1.0, 3.0), (-1.0, 3.0), ("1.0", "3.0")])
def test_integral_tws_modes_are_converted_when_parsing_request(n, m, monkeypatch, tmp_path):
    parsed_modes = []

    def inspect_simulation(simulation):
        header = simulation.cavities[0].field_table.traveling_wave
        parsed_modes.extend([header.n, header.m])
        return "simulation stub"

    monkeypatch.setattr(main, "process_simulation_input", inspect_simulation)
    status, _, data = put_simulation({"cavities": [{"field_table": {
        "z": [0, 1], "v": [0, 1],
        "traveling_wave": {"z1": 0.1, "z2": 0.9, "n": n, "m": m},
    }}]})

    assert status == 200, data
    assert parsed_modes == [int(float(n)), int(float(m))]
    assert all(type(value) is int for value in parsed_modes)
    field_map = next(tmp_path.glob("*/TWS_C1_E.dat"))
    assert field_map.read_text().splitlines()[0] == f"0.1 0.9 {parsed_modes[0]} {parsed_modes[1]}"
