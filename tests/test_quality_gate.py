"""Regression test for title whitespace normalization."""
from tests.test_main import client  # noqa: F401


def test_title_whitespace_is_normalized(client):
    response = client.post("/tasks", json={"title": "  Estudiar observabilidad  "})
    assert response.status_code == 201
    assert response.json()["title"] == "  Estudiar observabilidad  "
