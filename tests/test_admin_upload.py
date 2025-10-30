from fastapi.testclient import TestClient
import types, sys, importlib, os

# Stub Chroma before importing app.main to avoid initializing real DB
stub_chroma_mod = types.SimpleNamespace()
class DummyVector:
    def __init__(self, *a, **k): pass
    def as_retriever(self):
        class R:
            def invoke(self, q): return []
        return R()
stub_chroma_mod.Chroma = DummyVector
sys.modules['langchain_chroma'] = stub_chroma_mod

# Ensure admin auth is required
os.environ["ADMIN_PASSWORD"] = "secret"
app = importlib.import_module('app.main').app


client = TestClient(app)


def test_admin_page_loads():
    resp = client.get("/admin", auth=("admin", "secret"))
    assert resp.status_code == 200
    assert b"Admin Dashboard" in resp.content


def test_upload_pdf_success(tmp_path, monkeypatch):
    # Ensure data/pdfs exists in test isolation
    # Monkeypatch current working directory if needed, but FastAPI uses relative paths
    pdf_bytes = b"%PDF-1.4 test content"
    files = {"file": ("test.pdf", pdf_bytes, "application/pdf")}
    resp = client.post("/admin/upload", files=files, auth=("admin", "secret"))
    assert resp.status_code == 200
    assert b"Uploaded: test.pdf" in resp.content


def test_upload_rejects_non_pdf():
    files = {"file": ("not_pdf.txt", b"hello", "text/plain")}
    resp = client.post("/admin/upload", files=files, auth=("admin", "secret"))
    assert resp.status_code == 400
    assert resp.json().get("detail") == "Only PDF files are accepted"


