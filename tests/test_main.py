"""No AWS calls or RDS credentials are needed by these unit tests."""
from datetime import datetime

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool

from src.main import Base, create_app


class Metrics:
    def __init__(self):
        self.samples = []

    def start(self):
        pass

    def stop(self):
        pass

    def emit(self, *args):
        self.samples.append(args)


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setenv("APP_VERSION", "v1.0.0")
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    with TestClient(create_app(lambda: engine, Metrics())) as test_client:
        yield test_client
    engine.dispose()


def test_initial_tasks_empty(client):
    response = client.get("/tasks")
    assert response.status_code == 200
    assert response.json() == []


def test_create_and_read_task(client):
    response = client.post("/tasks", json={"title": "Estudiar Terraform", "done": False})
    assert response.status_code == 201
    task = response.json()
    assert task["title"] == "Estudiar Terraform" and task["done"] is False
    assert task["id"] > 0
    assert client.get("/tasks").json() == [task]


@pytest.mark.parametrize("title", ["", "   ", "x" * 201])
def test_reject_invalid_title(client, title):
    assert client.post("/tasks", json={"title": title}).status_code == 422
    assert client.get("/tasks").json() == []


def test_version_reads_environment(client):
    assert client.get("/version").json() == {"version": "v1.0.0"}


def test_health_includes_database_version_timestamp(client):
    result = client.get("/health")
    assert result.status_code == 200
    assert result.json()["database"] == "OK"
    assert result.json()["version"] == "v1.0.0"
    assert datetime.fromisoformat(result.json()["timestamp"]).tzinfo is not None


def test_failed_database_health_emits_error():
    def broken():
        raise ConnectionError("unreachable")
    metrics = Metrics()
    with TestClient(create_app(broken, metrics)) as client:
        response = client.get("/health")
    assert response.status_code == 503
    assert response.json()["database"] == "FAIL"
    assert ("DatabaseErrors", 1) in metrics.samples


@pytest.mark.parametrize("method,payload", [("get", None), ("post", {"title": "test"})])
def test_failed_read_or_write_returns_503(method, payload):
    def broken():
        raise ConnectionError("unreachable")
    metrics = Metrics()
    with TestClient(create_app(broken, metrics)) as client:
        response = client.request(method, "/tasks", json=payload)
    assert response.status_code == 503
    assert ("DatabaseErrors", 1) in metrics.samples


def test_success_emits_zero_error_and_latency(client):
    client.get("/tasks")
    samples = client.app.state.metrics.samples
    assert ("DatabaseErrors", 0) in samples
    assert any(sample[0] == "DatabaseLatency" and sample[1] >= 0 for sample in samples)


def test_title_whitespace_is_normalized(client):
    response = client.post("/tasks", json={"title": "  Estudiar observabilidad  "})
    assert response.status_code == 201
    assert response.json()["title"] == "Estudiar observabilidad"
