"""
Tests for file size limits on uploads.
"""
import pytest
import types
import sys
from fastapi.testclient import TestClient
from io import BytesIO


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


def test_upload_file_size_limit_exceeded(monkeypatch, test_client):
    """Test that files exceeding size limit are rejected."""
    import app.main as main
    from app.security_utils import MAX_UPLOAD_SIZE
    
    def mock_add_pdf_to_db(pdf_path):
        return 1
    
    monkeypatch.setattr(main, "add_pdf_to_db", mock_add_pdf_to_db)
    
    # Create a file larger than the limit (51 MB)
    large_file_size = MAX_UPLOAD_SIZE + (1024 * 1024)  # 51 MB
    large_file = BytesIO(b"x" * large_file_size)
    large_file.name = "large_file.pdf"
    
    response = test_client.post(
        "/upload",
        files={"file": ("large_file.pdf", large_file, "application/pdf")}
    )
    
    assert response.status_code == 413
    assert "exceeds maximum" in response.json()["detail"].lower()


def test_upload_file_size_within_limit(monkeypatch, test_client):
    """Test that files within size limit are accepted."""
    import app.main as main
    from pypdf import PdfWriter
    from io import BytesIO
    
    def mock_add_pdf_to_db(pdf_path):
        return 1
    
    monkeypatch.setattr(main, "add_pdf_to_db", mock_add_pdf_to_db)
    
    # Create a valid PDF file within the limit (5 MB)
    # We'll create a PDF with content to reach ~5MB
    writer = PdfWriter()
    # Add multiple pages to reach size
    small_file_size = 5 * 1024 * 1024  # 5 MB target
    page_size = 100 * 1024  # Approximate size per page
    num_pages = max(1, small_file_size // page_size)
    
    for _ in range(min(num_pages, 50)):  # Limit to 50 pages max
        writer.add_blank_page(width=200, height=200)
    
    buffer = BytesIO()
    writer.write(buffer)
    pdf_bytes = buffer.getvalue()
    
    response = test_client.post(
        "/upload",
        files={"file": ("small_file.pdf", pdf_bytes, "application/pdf")}
    )
    
    assert response.status_code == 200


def test_admin_upload_file_size_limit_exceeded(test_client, monkeypatch):
    """Test that admin upload rejects files exceeding size limit."""
    import app.main as main
    
    monkeypatch.setenv("ADMIN_PASSWORD", "")
    monkeypatch.setattr(main, "_maybe_convert_pdf_to_markdown", lambda x: None)
    
    from app.security_utils import MAX_UPLOAD_SIZE
    
    large_file_size = MAX_UPLOAD_SIZE + (1024 * 1024)  # 51 MB
    large_file = BytesIO(b"x" * large_file_size)
    large_file.name = "large_file.pdf"
    
    response = test_client.post(
        "/admin/upload",
        files={"file": ("large_file.pdf", large_file, "application/pdf")},
        auth=("admin", "")
    )
    
    assert response.status_code == 413
    assert "exceeds maximum" in response.json()["detail"].lower()


def test_validate_file_size_function():
    """Test the validate_file_size utility function."""
    from app.security_utils import validate_file_size, MAX_UPLOAD_SIZE
    
    # Should pass for valid size
    validate_file_size(10 * 1024 * 1024)  # 10 MB
    
    # Should raise for oversized file
    with pytest.raises(ValueError, match="exceeds maximum"):
        validate_file_size(MAX_UPLOAD_SIZE + 1)

