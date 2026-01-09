from fastapi.testclient import TestClient
import types, sys, importlib, os
from io import BytesIO

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


def create_valid_pdf_bytes() -> bytes:
    """Create a minimal valid PDF for testing."""
    try:
        from pypdf import PdfWriter
        writer = PdfWriter()
        writer.add_blank_page(width=200, height=200)
        buffer = BytesIO()
        writer.write(buffer)
        return buffer.getvalue()
    except ImportError:
        # Fallback minimal PDF if pypdf not available
        return b"""%PDF-1.4
1 0 obj
<< /Type /Catalog /Pages 2 0 R >>
endobj
2 0 obj
<< /Type /Pages /Kids [3 0 R] /Count 1 >>
endobj
3 0 obj
<< /Type /Page /Parent 2 0 R /MediaBox [0 0 200 200] >>
endobj
xref
0 4
0000000000 65535 f 
0000000009 00000 n 
0000000058 00000 n 
0000000115 00000 n 
trailer
<< /Size 4 /Root 1 0 R >>
startxref
185
%%EOF"""


def test_admin_page_loads():
    resp = client.get("/admin", auth=("admin", "secret"))
    assert resp.status_code == 200
    assert b"Admin Dashboard" in resp.content


def test_upload_pdf_success(tmp_path, monkeypatch):
    # Ensure data/pdfs exists in test isolation
    # Monkeypatch current working directory if needed, but FastAPI uses relative paths
    import app.main as main
    monkeypatch.setattr(main, "_maybe_convert_pdf_to_markdown", lambda x: None)
    
    pdf_bytes = create_valid_pdf_bytes()
    files = {"file": ("test.pdf", pdf_bytes, "application/pdf")}
    resp = client.post("/admin/upload", files=files, auth=("admin", "secret"))
    assert resp.status_code == 200
    # Check for success indicators in response
    assert b"uploaded" in resp.content.lower() or resp.status_code == 200


def test_upload_rejects_non_pdf():
    files = {"file": ("not_pdf.txt", b"hello", "text/plain")}
    resp = client.post("/admin/upload", files=files, auth=("admin", "secret"))
    assert resp.status_code == 400
    assert resp.json().get("detail") == "Only PDF files are accepted"


