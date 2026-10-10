import pytest
from fastapi.testclient import TestClient
from server import app


@pytest.fixture
def client():
    return TestClient(app)


def test_read_root(client):
    response = client.get("/")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_get_profiles(client):
    response = client.get("/profiles")
    assert response.status_code == 200
    profiles = response.json()["profiles"]
    assert "amiguito" in profiles
