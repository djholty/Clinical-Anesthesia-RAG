import os
import types
import pytest


@pytest.fixture(autouse=True)
def set_env(tmp_path, monkeypatch):
    monkeypatch.setenv("DB_DIR", str(tmp_path / "chroma_db"))
    monkeypatch.setenv("GROQ_API_KEY", "dummy")
    monkeypatch.setenv("HF_TOKEN", "dummy")


def test_query_rag_insufficient_context(monkeypatch):
    import app.rag_pipeline as rp

    class DummyRetriever:
        def invoke(self, q):
            return []

    monkeypatch.setattr(rp, "retriever", DummyRetriever())
    res = rp.query_rag("What is X?")
    low = res["answer"].lower()
    assert "does not provide" in low and "sufficient information" in low
    assert res["contexts"] == []


def test_query_rag_sanitizes_citations(monkeypatch):
    import app.rag_pipeline as rp

    class Doc:
        def __init__(self, content, source):
            self.page_content = content
            self.metadata = {"source": source, "page": 1}

    class DummyRetriever:
        def invoke(self, q):
            return [Doc("ctx", "allowed.pdf")]

    class DummyLLM:
        def invoke(self, messages):
            class R: pass
            r = R()
            r.content = "Answer. [Source: allowed.pdf] [Source: madeup.pdf]"
            return r

    monkeypatch.setattr(rp, "retriever", DummyRetriever())
    monkeypatch.setattr(rp, "llm", DummyLLM())
    res = rp.query_rag("Q")
    assert "allowed.pdf" in res["answer"]
    assert "madeup.pdf" not in res["answer"]


def test_add_and_list_and_delete(monkeypatch, tmp_path):
    import app.rag_pipeline as rp

    # Mock PyPDFLoader -> returns one doc
    class DummyLoader:
        def __init__(self, p):
            self.p = p
        def load(self):
            class D:
                page_content = "content"
                metadata = {"source": "file.pdf"}
            return [D()]

    # Mock DB collection methods
    class DummyCollection:
        def __init__(self):
            self.items = {"ids": ["1"], "metadatas": [{"source": "path/file.pdf"}]}
        def get(self, include=None):
            return self.items
        def delete(self, ids=None):
            self.items = {"ids": [], "metadatas": []}

    class DummyVector:
        def __init__(self):
            self._collection = DummyCollection()
        def add_documents(self, chunks):
            pass
        def as_retriever(self):
            return object()

    monkeypatch.setattr(rp, "PyPDFLoader", DummyLoader)
    dv = DummyVector()
    monkeypatch.setattr(rp, "vectordb", dv)

    added = rp.add_pdf_to_db("/tmp/file.pdf")
    assert added >= 1

    docs = rp.list_documents()
    assert docs == ["file.pdf"]

    res = rp.delete_document("file.pdf")
    assert res["deleted"] >= 0

