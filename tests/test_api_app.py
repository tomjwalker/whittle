from __future__ import annotations

from fastapi.testclient import TestClient

from whittle.api.app import create_app


def test_health_endpoint(monkeypatch) -> None:
    monkeypatch.delenv("WHITTLE_LOGFIRE_ENABLED", raising=False)
    client = TestClient(create_app())

    response = client.get("/health")

    assert response.status_code == 200
    assert response.json()["ok"] is True
    assert response.json()["logfire_enabled"] is False


def test_plan_endpoint_deterministic() -> None:
    client = TestClient(create_app())

    response = client.post(
        "/api/plan",
        json={
            "message": "Set up cruise at 5 m/s with spinning propellers.",
            "case_name": "api_test",
            "deterministic": True,
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ready_for_human_review"
    assert payload["scenario_plan"]["spec"]["rotor_model"] == "mrf"


def test_plan_endpoint_accepts_previous_plan_for_follow_up() -> None:
    client = TestClient(create_app())

    first = client.post(
        "/api/plan",
        json={
            "message": "Set up cruise at 5 m/s with spinning propellers.",
            "case_name": "api_memory",
            "deterministic": True,
        },
    )
    assert first.status_code == 200

    response = client.post(
        "/api/plan",
        json={
            "message": "Make it faster at 10 m/s.",
            "case_name": "api_memory",
            "deterministic": True,
            "previous_plan": first.json()["scenario_plan"],
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["scenario_plan"]["spec"]["reference_velocity_mps"] == 10
    assert payload["scenario_plan"]["spec"]["rotor_model"] == "mrf"
