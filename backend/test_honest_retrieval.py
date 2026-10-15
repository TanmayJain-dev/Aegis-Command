import os
import sys
import pytest
from fastapi.testclient import TestClient

# Ensure backend directory is in path
sys.path.insert(0, os.path.dirname(__file__))

# Import app from main
from main import app, startup_event

client = TestClient(app)


@pytest.fixture(scope="module", autouse=True)
def init_backend():
    # Trigger startup event synchronously to index mock intel
    import asyncio
    asyncio.run(startup_event())


def test_query_truck():
    """Query 'truck' returns relevant pickup truck intercept with normalized score."""
    response = client.post("/api/intel/search", json={"query": "truck"})
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "success"
    assert len(data["data"]) > 0
    top = data["data"][0]
    assert top["id"] == "INTEL-9999"
    assert 0.0 <= top["score"] <= 1.0
    assert top["score"] >= 0.20


def test_query_person_moving():
    """Query 'person moving NE' returns relevant patrol/movement intel with normalized score."""
    response = client.post("/api/intel/search", json={"query": "person moving NE"})
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "success"
    assert len(data["data"]) > 0
    top = data["data"][0]
    assert 0.0 <= top["score"] <= 1.0
    assert top["score"] >= 0.20


def test_query_drone():
    """Query 'drone' returns relevant aerial/drone intel with normalized score."""
    response = client.post("/api/intel/search", json={"query": "drone"})
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "success"
    assert len(data["data"]) > 0
    top = data["data"][0]
    assert 0.0 <= top["score"] <= 1.0
    assert top["score"] >= 0.20


def test_query_banana_irrelevant():
    """Irrelevant query 'banana' returns explicit zero-result response without top-k noise."""
    response = client.post("/api/intel/search", json={"query": "banana"})
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "success"
    assert len(data["data"]) == 0
    assert "no relevant intel found" in data["message"].lower()


def test_query_asdf_irrelevant():
    """Gibberish query 'asdf' returns explicit zero-result response without top-k noise."""
    response = client.post("/api/intel/search", json={"query": "asdf"})
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "success"
    assert len(data["data"]) == 0
    assert "no relevant intel found" in data["message"].lower()
