from __future__ import annotations

from fastapi.testclient import TestClient

from whittle.api.app import create_app


def test_health_endpoint() -> None:
    client = TestClient(create_app())

    response = client.get("/health")

    assert response.status_code == 200
    assert response.json()["ok"] is True


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
