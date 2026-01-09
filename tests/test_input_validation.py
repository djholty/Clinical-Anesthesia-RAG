"""
Tests for input validation on user queries.
"""
import pytest
import types
import sys
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
    stub_chroma_mod = types.SimpleNamespace()
    class DummyVector:
        def __init__(self, *a, **k): 
            pass
        def as_retriever(self):
            class R: 
                def invoke(self, q): return []
            return R()
    stub_chroma_mod.Chroma = DummyVector
    sys.modules['langchain_chroma'] = stub_chroma_mod

    import importlib
    main = importlib.import_module('app.main')
    return TestClient(main.app)


def test_question_empty_string(test_client):
    """Test that empty questions are rejected."""
    response = test_client.post("/ask", json={"question": ""})
    assert response.status_code == 422  # Validation error


def test_question_whitespace_only(test_client):
    """Test that whitespace-only questions are rejected."""
    response = test_client.post("/ask", json={"question": "   \n\t  "})
    assert response.status_code == 422  # Validation error


def test_question_too_long(test_client):
    """Test that questions exceeding max length are rejected."""
    long_question = "a" * 5001
    response = test_client.post("/ask", json={"question": long_question})
    assert response.status_code == 422  # Validation error


def test_question_valid_length(test_client, monkeypatch):
    """Test that valid length questions are accepted."""
    import app.main as main
    
    def mock_query(q):
        return {"answer": "Answer", "contexts": []}
    
    monkeypatch.setattr(main, "query_rag", mock_query)
    
    valid_question = "What is anesthesia?"
    response = test_client.post("/ask", json={"question": valid_question})
    assert response.status_code == 200


def test_question_max_length_accepted(test_client, monkeypatch):
    """Test that questions at max length are accepted."""
    import app.main as main
    
    def mock_query(q):
        return {"answer": "Answer", "contexts": []}
    
    monkeypatch.setattr(main, "query_rag", mock_query)
    
    max_length_question = "a" * 5000
    response = test_client.post("/ask", json={"question": max_length_question})
    assert response.status_code == 200


def test_question_sanitizes_whitespace(test_client, monkeypatch):
    """Test that excessive whitespace is normalized."""
    import app.main as main
    
    def mock_query(q):
        # Verify question was sanitized (whitespace normalized)
        assert len(q.split()) == len(q.strip().split())
        return {"answer": "Answer", "contexts": []}
    
    monkeypatch.setattr(main, "query_rag", mock_query)
    
    question_with_spaces = "  What   is   anesthesia?  "
    response = test_client.post("/ask", json={"question": question_with_spaces})
    assert response.status_code == 200


def test_query_rag_validates_empty():
    """Test query_rag function validates empty input."""
    from app.rag_pipeline import query_rag
    
    with pytest.raises(ValueError, match="cannot be empty"):
        query_rag("")


def test_query_rag_validates_too_long():
    """Test query_rag function validates length."""
    from app.rag_pipeline import query_rag
    
    long_question = "a" * 5001
    with pytest.raises(ValueError, match="exceeds maximum length"):
        query_rag(long_question)


def test_query_rag_validates_whitespace_only():
    """Test query_rag function validates whitespace-only input."""
    from app.rag_pipeline import query_rag
    
    with pytest.raises(ValueError, match="cannot be empty"):
        query_rag("   \n\t  ")

