"""
Extended RAG pipeline tests covering format_docs and edge cases.
"""
import os
import pytest
from unittest.mock import Mock


@pytest.fixture(autouse=True)
def set_env(tmp_path, monkeypatch):
    """Set up environment variables for testing."""
    monkeypatch.setenv("DB_DIR", str(tmp_path / "chroma_db"))
    monkeypatch.setenv("GROQ_API_KEY", "dummy")
    monkeypatch.setenv("HF_TOKEN", "dummy")


def test_format_docs_with_source():
    """Test format_docs function with documents that have source metadata."""
    import app.rag_pipeline as rp
    
    # Create mock documents
    doc1 = Mock()
    doc1.metadata = {"source": "/path/to/file1.pdf"}
    doc1.page_content = "Content 1"
    
    doc2 = Mock()
    doc2.metadata = {"source": "/another/path/to/file2.pdf"}
    doc2.page_content = "Content 2"
    
    docs = [doc1, doc2]
    result = rp.format_docs(docs)
    
    assert "[Source: file1.pdf]" in result
    assert "[Source: file2.pdf]" in result
    assert "Content 1" in result
    assert "Content 2" in result


def test_format_docs_without_source():
    """Test format_docs function with documents missing source metadata."""
    import app.rag_pipeline as rp
    
    doc1 = Mock()
    doc1.metadata = {}  # No source
    doc1.page_content = "Content 1"
    
    doc2 = Mock()
    doc2.metadata = None  # No metadata at all
    doc2.page_content = "Content 2"
    
    docs = [doc1, doc2]
    result = rp.format_docs(docs)
    
    assert "[Source: Unknown source]" in result
    assert "Content 1" in result
    assert "Content 2" in result


def test_format_docs_with_source_no_slash():
    """Test format_docs function with source that has no slash."""
    import app.rag_pipeline as rp
    
    doc = Mock()
    doc.metadata = {"source": "simple_file.pdf"}
    doc.page_content = "Content"
    
    result = rp.format_docs([doc])
    
    assert "[Source: simple_file.pdf]" in result
    assert "Content" in result


def test_format_docs_empty_list():
    """Test format_docs function with empty document list."""
    import app.rag_pipeline as rp
    
    result = rp.format_docs([])
    assert result == ""


def test_format_docs_multiple_docs_separated():
    """Test format_docs properly separates multiple documents."""
    import app.rag_pipeline as rp
    
    doc1 = Mock()
    doc1.metadata = {"source": "file1.pdf"}
    doc1.page_content = "Content 1"
    
    doc2 = Mock()
    doc2.metadata = {"source": "file2.pdf"}
    doc2.page_content = "Content 2"
    
    result = rp.format_docs([doc1, doc2])
    
    # Should have double newline separation
    parts = result.split("\n\n")
    assert len(parts) >= 2
    assert "file1.pdf" in parts[0]
    assert "file2.pdf" in parts[1]

