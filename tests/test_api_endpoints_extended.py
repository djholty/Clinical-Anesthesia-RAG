"""
Extended API endpoint tests covering missing endpoints and error handling.
"""
import os
import types
import sys
import pytest
from fastapi.testclient import TestClient


@pytest.fixture(autouse=True)
def set_env(tmp_path, monkeypatch):
    """Set up environment variables for testing."""
    monkeypatch.setenv("GROQ_API_KEY", "dummy")
    monkeypatch.setenv("HF_TOKEN", "dummy")
    monkeypatch.setenv("DB_DIR", str(tmp_path / "chroma_db"))


@pytest.fixture
def test_client():
    """Create a test client with mocked Chroma."""
    # Stub Chroma before importing app.main
    stub_chroma_mod = types.SimpleNamespace()
    class DummyVector:
        def __init__(self, *a, **k): 
            pass
        def as_retriever(self):
            class R: 
                def invoke(self, q): 
                    return []
            return R()
    stub_chroma_mod.Chroma = DummyVector
    sys.modules['langchain_chroma'] = stub_chroma_mod

    import importlib
    main = importlib.import_module('app.main')
    return TestClient(main.app)


def test_home_endpoint(test_client):
    """Test the home endpoint returns correct message."""
    resp = test_client.get("/")
    assert resp.status_code == 200
    data = resp.json()
    assert "message" in data
    assert "Clinical Anesthesia QA System" in data["message"]


def test_health_endpoint(test_client):
    """Test the health check endpoint."""
    resp = test_client.get("/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "healthy"
    assert data["server"] == "running"
    assert "evaluation_status" in data


def test_ask_endpoint_api_key_error(monkeypatch, test_client):
    """Test API endpoint handles API key errors correctly."""
    import app.main as main
    
    def fake_query_raises_key_error(q):
        raise Exception("Invalid API key")
    
    monkeypatch.setattr(main, "query_rag", fake_query_raises_key_error)
    
    resp = test_client.post("/ask", json={"question": "What is anesthesia?"})
    assert resp.status_code == 401
    # Updated: Generic error messages don't expose API key details for security
    assert "authentication" in resp.json()["detail"].lower() or "failed" in resp.json()["detail"].lower()


def test_ask_endpoint_timeout_error(monkeypatch, test_client):
    """Test API endpoint handles timeout errors correctly."""
    import app.main as main
    
    def fake_query_raises_timeout(q):
        raise Exception("Request timed out")
    
    monkeypatch.setattr(main, "query_rag", fake_query_raises_timeout)
    
    resp = test_client.post("/ask", json={"question": "What is anesthesia?"})
    assert resp.status_code == 504
    assert "timeout" in resp.json()["detail"].lower()


def test_ask_endpoint_rate_limit_error(monkeypatch, test_client):
    """Test API endpoint handles rate limit errors correctly."""
    import app.main as main
    
    def fake_query_raises_rate_limit(q):
        raise Exception("429 rate limit exceeded")
    
    monkeypatch.setattr(main, "query_rag", fake_query_raises_rate_limit)
    
    resp = test_client.post("/ask", json={"question": "What is anesthesia?"})
    assert resp.status_code == 429
    assert "rate limit" in resp.json()["detail"].lower() or "quota" in resp.json()["detail"].lower()


def test_ask_endpoint_over_capacity_error(monkeypatch, test_client):
    """Test API endpoint handles over capacity errors correctly."""
    import app.main as main
    
    def fake_query_raises_over_capacity(q):
        raise Exception("503 over capacity")
    
    monkeypatch.setattr(main, "query_rag", fake_query_raises_over_capacity)
    
    resp = test_client.post("/ask", json={"question": "What is anesthesia?"})
    assert resp.status_code == 503
    # Updated: Generic error message doesn't expose capacity details
    assert "unavailable" in resp.json()["detail"].lower() or "try again" in resp.json()["detail"].lower()


def test_ask_endpoint_generic_error(monkeypatch, test_client):
    """Test API endpoint handles generic errors correctly."""
    import app.main as main
    
    def fake_query_raises_generic(q):
        raise Exception("Something went wrong")
    
    monkeypatch.setattr(main, "query_rag", fake_query_raises_generic)
    
    resp = test_client.post("/ask", json={"question": "What is anesthesia?"})
    assert resp.status_code == 500
    # Updated: Generic error message doesn't expose internal details
    assert "error occurred" in resp.json()["detail"].lower() or "try again" in resp.json()["detail"].lower()


def test_monitoring_latest_endpoint(monkeypatch, test_client):
    """Test /monitoring/latest endpoint."""
    import app.main as main
    from app.monitoring import get_latest_evaluation
    
    mock_result = {
        "timestamp": "20250101_010101",
        "total_questions": 10,
        "average_score": 3.5
    }
    
    # Patch the imported function in main module
    monkeypatch.setattr(main, "get_latest_evaluation", lambda: mock_result)
    
    resp = test_client.get("/monitoring/latest")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total_questions"] == 10


def test_monitoring_latest_endpoint_no_results(monkeypatch, test_client):
    """Test /monitoring/latest endpoint when no results exist."""
    import app.main as main
    from app.monitoring import get_latest_evaluation
    
    # Patch the imported function in main module
    monkeypatch.setattr(main, "get_latest_evaluation", lambda: None)
    
    resp = test_client.get("/monitoring/latest")
    assert resp.status_code == 200
    assert "error" in resp.json()


def test_monitoring_all_endpoint(monkeypatch, test_client):
    """Test /monitoring/all endpoint."""
    import app.main as main
    from app.monitoring import get_all_evaluations
    
    mock_evaluations = [
        {"timestamp": "20250101_010101", "average_score": 3.5},
        {"timestamp": "20250102_020202", "average_score": 4.0}
    ]
    
    # Patch the imported function in main module
    monkeypatch.setattr(main, "get_all_evaluations", lambda: mock_evaluations)
    
    resp = test_client.get("/monitoring/all")
    assert resp.status_code == 200
    data = resp.json()
    assert "evaluations" in data
    assert len(data["evaluations"]) == 2


def test_monitoring_evaluation_status_endpoint(test_client):
    """Test /monitoring/evaluation_status endpoint."""
    resp = test_client.get("/monitoring/evaluation_status")
    assert resp.status_code == 200
    data = resp.json()
    assert "is_running" in data
    assert "status" in data
    assert "progress_percent" in data


def test_monitoring_timestamp_endpoint(monkeypatch, test_client):
    """Test /monitoring/{timestamp} endpoint."""
    import app.main as main
    from app.monitoring import get_evaluation_by_timestamp
    
    mock_result = {
        "timestamp": "20250101_010101",
        "total_questions": 10,
        "average_score": 3.5
    }
    
    # Patch the imported function in main module
    monkeypatch.setattr(main, "get_evaluation_by_timestamp", lambda ts: mock_result)
    
    resp = test_client.get("/monitoring/20250101_010101")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total_questions"] == 10


def test_monitoring_timestamp_endpoint_not_found(monkeypatch, test_client):
    """Test /monitoring/{timestamp} endpoint when timestamp not found."""
    import app.main as main
    from app.monitoring import get_evaluation_by_timestamp
    
    # Patch the imported function in main module
    monkeypatch.setattr(main, "get_evaluation_by_timestamp", lambda ts: None)
    
    resp = test_client.get("/monitoring/99999999_999999")
    assert resp.status_code == 200
    assert "error" in resp.json()


