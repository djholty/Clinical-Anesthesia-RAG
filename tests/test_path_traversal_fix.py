"""
Tests to verify path traversal vulnerability is fixed.
"""
import pytest
import os
import tempfile
from pathlib import Path
from fastapi.testclient import TestClient
import types
import sys
import importlib


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
                def invoke(self, q): 
                    return []
            return R()
    stub_chroma_mod.Chroma = DummyVector
    sys.modules['langchain_chroma'] = stub_chroma_mod

    import importlib
    main = importlib.import_module('app.main')
    return TestClient(main.app)


def test_upload_path_traversal_blocked(monkeypatch, test_client, tmp_path):
    """Test that path traversal attacks are blocked in upload endpoint."""
    import app.main as main
    from pypdf import PdfWriter
    from io import BytesIO
    
    # Mock add_pdf_to_db to avoid actual PDF processing
    def mock_add_pdf_to_db(pdf_path):
        return 1
    
    monkeypatch.setattr(main, "add_pdf_to_db", mock_add_pdf_to_db)
    
    # Create a valid PDF file
    writer = PdfWriter()
    writer.add_blank_page(width=200, height=200)
    buffer = BytesIO()
    writer.write(buffer)
    valid_pdf = buffer.getvalue()
    
    uploads_dir = Path("uploads")
    
    # Create a malicious filename with path traversal
    malicious_filename = "../../../etc/passwd.pdf"  # Add .pdf so it passes extension check
    
    response = test_client.post(
        "/upload",
        files={"file": (malicious_filename, valid_pdf, "application/pdf")}
    )
    
    # Should accept the file but sanitize the filename
    assert response.status_code == 200
    
    # Verify file was saved with sanitized name, not in /etc
    # The sanitized name should be just "passwd.pdf"
    assert uploads_dir.exists()
    
    # Verify the sanitized filename was used in response
    data = response.json()
    assert data["filename"] == "passwd.pdf"  # Sanitized - just the basename
    
    # Verify file was saved with sanitized name in uploads directory
    saved_file = uploads_dir / "passwd.pdf"
    assert saved_file.exists()


def test_upload_path_traversal_windows_style_blocked(monkeypatch, test_client):
    """Test that Windows-style path traversal is blocked."""
    import app.main as main
    from pypdf import PdfWriter
    from io import BytesIO
    
    # Mock add_pdf_to_db
    def mock_add_pdf_to_db(pdf_path):
        return 1
    
    monkeypatch.setattr(main, "add_pdf_to_db", mock_add_pdf_to_db)
    
    # Create a valid PDF file
    writer = PdfWriter()
    writer.add_blank_page(width=200, height=200)
    buffer = BytesIO()
    writer.write(buffer)
    valid_pdf = buffer.getvalue()
    
    malicious_filename = "..\\..\\windows\\system32\\config\\sam.pdf"  # Add .pdf extension
    
    response = test_client.post(
        "/upload",
        files={"file": (malicious_filename, valid_pdf, "application/pdf")}
    )
    
    assert response.status_code == 200
    data = response.json()
    # Filename should be sanitized - no path separators
    assert "\\" not in data["filename"]
    assert ".." not in data["filename"]
    assert "/" not in data["filename"]  # No forward slashes either


def test_admin_upload_path_traversal_blocked(test_client, monkeypatch):
    """Test that path traversal is blocked in admin upload."""
    import app.main as main
    from pypdf import PdfWriter
    from io import BytesIO
    
    # Disable admin password for test
    monkeypatch.setenv("ADMIN_PASSWORD", "")
    
    # Mock the background conversion function
    def mock_convert(pdf_path):
        pass
    
    monkeypatch.setattr(main, "_maybe_convert_pdf_to_markdown", mock_convert)
    
    # Create a valid PDF file
    writer = PdfWriter()
    writer.add_blank_page(width=200, height=200)
    buffer = BytesIO()
    writer.write(buffer)
    valid_pdf = buffer.getvalue()
    
    # Use a malicious filename that will still be valid PDF after sanitization
    # "../../../etc/passwd.pdf" becomes "passwd.pdf" after sanitization
    malicious_filename = "../../../etc/passwd.pdf"
    
    response = test_client.post(
        "/admin/upload",
        files={"file": (malicious_filename, valid_pdf, "application/pdf")},
        auth=("admin", "")
    )
    
    # Should work but with sanitized filename
    assert response.status_code == 200
    # Verify the response contains sanitized filename
    assert b"passwd.pdf" in response.content or b"uploaded" in response.content.lower()
    
    # Verify file was saved in correct location (data/pdfs/passwd.pdf, not /etc/passwd.pdf)
    pdfs_dir = Path("./data/pdfs")
    if pdfs_dir.exists():
        # File should be in pdfs directory with sanitized name
        sanitized_file = pdfs_dir / "passwd.pdf"
        # The file should exist after successful upload
        assert sanitized_file.exists()


def test_delete_path_traversal_blocked(monkeypatch, test_client):
    """Test that path traversal is blocked in delete endpoint."""
    import app.main as main
    
    # Mock delete_document to avoid actual database operations
    def mock_delete_document(filename):
        # Verify filename was sanitized
        assert filename == "passwd"  # Should be sanitized
        return {"deleted": 0, "message": f"Deleted {filename}"}
    
    monkeypatch.setattr(main, "delete_document", mock_delete_document)
    
    malicious_filename = "../../../etc/passwd"
    
    response = test_client.request(
        "DELETE",
        "/delete_doc",
        json={"filename": malicious_filename}
    )
    
    # Should sanitize the filename before processing
    assert response.status_code == 200
    # The delete should use sanitized filename "passwd", not "../../../etc/passwd"
    data = response.json()
    assert "passwd" in data.get("message", "")

