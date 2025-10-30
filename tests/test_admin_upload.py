from fastapi.testclient import TestClient
from app.main import app


client = TestClient(app)


def test_admin_page_loads():
    resp = client.get("/admin")
    assert resp.status_code == 200
    assert b"Admin Dashboard" in resp.content


def test_upload_pdf_success(tmp_path, monkeypatch):
    # Ensure data/pdfs exists in test isolation
    # Monkeypatch current working directory if needed, but FastAPI uses relative paths
    pdf_bytes = b"%PDF-1.4 test content"
    files = {"file": ("test.pdf", pdf_bytes, "application/pdf")}
    resp = client.post("/admin/upload", files=files)
    assert resp.status_code == 200
    assert b"Uploaded: test.pdf" in resp.content


def test_upload_rejects_non_pdf():
    files = {"file": ("not_pdf.txt", b"hello", "text/plain")}
    resp = client.post("/admin/upload", files=files)
    assert resp.status_code == 400
    assert resp.json().get("detail") == "Only PDF files are accepted"


