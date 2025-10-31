import os
import pytest
import types
import sys
from fastapi.testclient import TestClient


@pytest.fixture(autouse=True)
def set_env(tmp_path, monkeypatch):
    monkeypatch.setenv("GROQ_API_KEY", "dummy")
    monkeypatch.setenv("HF_TOKEN", "dummy")
    monkeypatch.setenv("DB_DIR", str(tmp_path / "chroma_db"))


def test_ask_endpoint_success(monkeypatch):
    # Stub out Chroma at import time to avoid real DB initialization
    stub_chroma_mod = types.SimpleNamespace()
    class DummyVector:
        def __init__(self, *a, **k): pass
        def as_retriever(self):
            class R: 
                def invoke(self, q): return []
            return R()
    stub_chroma_mod.Chroma = DummyVector
    sys.modules['langchain_chroma'] = stub_chroma_mod

    import importlib
    main = importlib.import_module('app.main')
    client = TestClient(main.app)

    def fake_query(q):
        return {"answer": "A", "contexts": []}

    monkeypatch.setattr(main, "query_rag", fake_query)
    resp = client.post("/ask", json={"question": "Q"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["answer"] == "A"


def test_list_docs_and_delete(monkeypatch):
    # Stub Chroma to avoid side effects
    stub_chroma_mod = types.SimpleNamespace()
    class DummyVector:
        def __init__(self, *a, **k): pass
        def as_retriever(self):
            class R: 
                def invoke(self, q): return []
            return R()
    stub_chroma_mod.Chroma = DummyVector
    sys.modules['langchain_chroma'] = stub_chroma_mod

    import importlib
    main = importlib.import_module('app.main')
    client = TestClient(main.app)

    monkeypatch.setattr(main, "list_documents", lambda: ["a.pdf", "b.pdf"])
    r = client.get("/list_docs")
    assert r.status_code == 200
    assert set(r.json()["documents"]) == {"a.pdf", "b.pdf"}

    def fake_delete(name):
        return {"deleted": 2}

    monkeypatch.setattr(main, "delete_document", fake_delete)
    r2 = client.request("DELETE", "/delete_doc", json={"filename": "a.pdf"})
    assert r2.status_code == 200
    assert r2.json()["deleted"] == 2


def test_admin_auth_gate(monkeypatch):
    stub_chroma_mod = types.SimpleNamespace()
    class DummyVector:
        def __init__(self, *a, **k): pass
        def as_retriever(self):
            class R: 
                def invoke(self, q): return []
            return R()
    stub_chroma_mod.Chroma = DummyVector
    sys.modules['langchain_chroma'] = stub_chroma_mod

    import importlib
    main = importlib.import_module('app.main')
    client = TestClient(main.app)

    # Set password to require auth
    monkeypatch.setenv("ADMIN_PASSWORD", "secret")

    r = client.get("/admin")
    assert r.status_code == 401

    r2 = client.get("/admin", auth=("admin", "secret"))
    assert r2.status_code == 200

