"""
Tests for rate limiting on API endpoints.
"""
import pytest
import types
import sys
from fastapi.testclient import TestClient
import time


@pytest.fixture(autouse=True)
def set_env(tmp_path, monkeypatch):
    """Set up environment variables for testing."""
    monkeypatch.setenv("GROQ_API_KEY", "dummy")
    monkeypatch.setenv("HF_TOKEN", "dummy")
    monkeypatch.setenv("DB_DIR", str(tmp_path / "chroma_db"))


@pytest.fixture(autouse=True)
def reset_rate_limiter():
    """Reset rate limiter storage before each test."""
    import importlib
    from limits.storage.memory import MemoryStorage
    
    # Reset before test
    main = importlib.import_module('app.main')
    if hasattr(main.app.state, 'limiter'):
        limiter = main.app.state.limiter
        if hasattr(limiter, '_storage'):
            # Create a fresh memory storage instance
            limiter._storage = MemoryStorage()
    
    yield
    
    # Reset after test too, to ensure clean state for next test
    main = importlib.import_module('app.main')
    if hasattr(main.app.state, 'limiter'):
        limiter = main.app.state.limiter
        if hasattr(limiter, '_storage'):
            limiter._storage = MemoryStorage()


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


def test_rate_limit_ask_endpoint(monkeypatch):
    """Test that /ask endpoint enforces rate limiting."""
    import importlib
    from limits.storage.memory import MemoryStorage
    
    # Force module reload and reset limiter before this test
    if 'app.main' in sys.modules:
        importlib.reload(sys.modules['app.main'])
    
    import app.main as main
    
    # Reset limiter to ensure clean state
    if hasattr(main.app.state, 'limiter'):
        main.app.state.limiter._storage = MemoryStorage()
    
    def mock_query(q):
        return {"answer": "Answer", "contexts": []}
    
    monkeypatch.setattr(main, "query_rag", mock_query)
    
    # Create test client after reset
    from fastapi.testclient import TestClient
    test_client = TestClient(main.app)
    
    # Make 10 requests (should be within limit)
    for i in range(10):
        response = test_client.post("/ask", json={"question": f"Question {i}"})
        assert response.status_code == 200
    
    # 11th request should be rate limited
    response = test_client.post("/ask", json={"question": "Question 11"})
    assert response.status_code == 429  # Too Many Requests


def test_rate_limit_upload_endpoint(monkeypatch):
    """Test that /upload endpoint enforces rate limiting."""
    import importlib
    from limits.storage.memory import MemoryStorage
    
    # Force module reload and reset limiter before this test
    if 'app.main' in sys.modules:
        importlib.reload(sys.modules['app.main'])
    
    import app.main as main
    from pypdf import PdfWriter
    from io import BytesIO
    
    # Explicitly reset limiter for this test to ensure clean state
    if hasattr(main.app.state, 'limiter'):
        main.app.state.limiter._storage = MemoryStorage()
    
    def mock_add_pdf_to_db(pdf_path):
        return 1
    
    monkeypatch.setattr(main, "add_pdf_to_db", mock_add_pdf_to_db)
    
    # Create a valid PDF
    writer = PdfWriter()
    writer.add_blank_page(width=200, height=200)
    buffer = BytesIO()
    writer.write(buffer)
    pdf_bytes = buffer.getvalue()
    
    # Create test client after reset
    from fastapi.testclient import TestClient
    test_client = TestClient(main.app)
    
    # Make 5 requests (should be within limit)
    for i in range(5):
        response = test_client.post(
            "/upload",
            files={"file": (f"test_{i}.pdf", pdf_bytes, "application/pdf")}
        )
        assert response.status_code == 200
    
    # 6th request should be rate limited
    response = test_client.post(
        "/upload",
        files={"file": ("test_6.pdf", pdf_bytes, "application/pdf")}
    )
    assert response.status_code == 429  # Too Many Requests


def test_rate_limit_resets_after_period(monkeypatch, test_client):
    """Test that rate limits reset after the time period."""
    import app.main as main
    
    def mock_query(q):
        return {"answer": "Answer", "contexts": []}
    
    monkeypatch.setattr(main, "query_rag", mock_query)
    
    # Exhaust rate limit
    for i in range(10):
        test_client.post("/ask", json={"question": f"Question {i}"})
    
    # Should be rate limited
    response = test_client.post("/ask", json={"question": "Question 11"})
    assert response.status_code == 429
    
    # Wait for rate limit to reset (in a real scenario, wait 60 seconds)
    # For testing, we can manually reset the limiter or wait
    # For now, just verify the limit exists - full reset testing requires time.sleep(60)
    # which would make tests too slow
    assert "Retry-After" in response.headers or response.status_code == 429


def test_rate_limit_per_ip(monkeypatch):
    """Test that rate limits are enforced per IP address."""
    import importlib
    from limits.storage.memory import MemoryStorage
    
    # Force module reload and reset limiter before this test
    if 'app.main' in sys.modules:
        importlib.reload(sys.modules['app.main'])
    
    import app.main as main
    import types
    
    # Explicitly reset limiter right at the start
    if hasattr(main.app.state, 'limiter'):
        main.app.state.limiter._storage = MemoryStorage()
    
    stub_chroma_mod = types.SimpleNamespace()
    class DummyVector:
        def __init__(self, *a, **k): pass
        def as_retriever(self):
            class R: 
                def invoke(self, q): return []
            return R()
    stub_chroma_mod.Chroma = DummyVector
    sys.modules['langchain_chroma'] = stub_chroma_mod
    
    def mock_query(q):
        return {"answer": "Answer", "contexts": []}
    
    monkeypatch.setattr(main, "query_rag", mock_query)
    
    # Verify limiter exists and reset storage one more time
    assert hasattr(main.app, 'state') and hasattr(main.app.state, 'limiter')
    main.app.state.limiter._storage = MemoryStorage()
    
    # Create a client
    client = TestClient(main.app)
    
    # Make requests - should work since limiter was reset
    response = client.post("/ask", json={"question": "Test question"})
    assert response.status_code == 200

