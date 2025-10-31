"""
Tests for rebuild_database function.
"""
import os
import shutil
import pytest
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock


@pytest.fixture(autouse=True)
def set_env(tmp_path, monkeypatch):
    """Set up environment variables for testing."""
    monkeypatch.setenv("HF_TOKEN", "dummy")
    monkeypatch.setenv("MARKDOWN_DIR", str(tmp_path / "markdown"))
    monkeypatch.setenv("DB_DIR", str(tmp_path / "chroma_db"))
    monkeypatch.setenv("OLD_DB_DIR", str(tmp_path / "old_db"))


def test_rebuild_database_removes_old_database(tmp_path, monkeypatch):
    """Test that rebuild_database removes old database directories."""
    from app.rebuild_database import rebuild_database
    
    # Create fake old databases
    db_dir = tmp_path / "chroma_db"
    old_db_dir = tmp_path / "old_db"
    db_dir.mkdir()
    old_db_dir.mkdir()
    
    # Create some fake files
    (db_dir / "some_file").write_text("test")
    (old_db_dir / "some_file").write_text("test")
    
    # Create markdown directory with test file
    md_dir = tmp_path / "markdown"
    md_dir.mkdir()
    (md_dir / "test.md").write_text("# Test Document\n\nThis is a test.")
    
    with patch('app.rebuild_database.DirectoryLoader') as MockLoader, \
         patch('app.rebuild_database.Chroma') as MockChroma, \
         patch('app.rebuild_database.HuggingFaceEmbeddings') as MockEmbeddings, \
         patch('app.rebuild_database.RecursiveCharacterTextSplitter') as MockSplitter:
        
        # Mock loader
        mock_loader = Mock()
        mock_doc = Mock()
        mock_doc.page_content = "# Test Document\n\nThis is a test."
        mock_doc.metadata = {"source": str(md_dir / "test.md")}
        mock_loader.load.return_value = [mock_doc]
        MockLoader.return_value = mock_loader
        
        # Mock splitter
        mock_splitter = Mock()
        mock_splitter.split_documents.return_value = [mock_doc]
        MockSplitter.return_value = mock_splitter
        
        # Mock embeddings
        mock_embeddings = Mock()
        MockEmbeddings.return_value = mock_embeddings
        
        # Mock Chroma
        mock_chroma = Mock()
        MockChroma.from_documents.return_value = mock_chroma
        
        # Run rebuild
        rebuild_database(str(md_dir), str(db_dir))
        
        # Verify old directories were removed
        assert not db_dir.exists() or len(list(db_dir.iterdir())) == 0, "Old DB should be removed"


def test_rebuild_database_loads_markdown_files(tmp_path, monkeypatch):
    """Test that rebuild_database loads markdown files correctly."""
    from app.rebuild_database import rebuild_database
    
    # Create markdown directory with test files
    md_dir = tmp_path / "markdown"
    md_dir.mkdir()
    (md_dir / "test1.md").write_text("# Document 1\n\nContent 1.")
    (md_dir / "test2.md").write_text("# Document 2\n\nContent 2.")
    
    db_dir = tmp_path / "chroma_db"
    
    with patch('app.rebuild_database.DirectoryLoader') as MockLoader, \
         patch('app.rebuild_database.Chroma') as MockChroma, \
         patch('app.rebuild_database.HuggingFaceEmbeddings') as MockEmbeddings, \
         patch('app.rebuild_database.RecursiveCharacterTextSplitter') as MockSplitter:
        
        # Mock loader
        mock_loader = Mock()
        mock_doc1 = Mock()
        mock_doc1.page_content = "# Document 1\n\nContent 1."
        mock_doc1.metadata = {"source": str(md_dir / "test1.md")}
        mock_doc2 = Mock()
        mock_doc2.page_content = "# Document 2\n\nContent 2."
        mock_doc2.metadata = {"source": str(md_dir / "test2.md")}
        mock_loader.load.return_value = [mock_doc1, mock_doc2]
        MockLoader.return_value = mock_loader
        
        # Mock splitter
        mock_splitter = Mock()
        mock_splitter.split_documents.return_value = [mock_doc1, mock_doc2]
        MockSplitter.return_value = mock_splitter
        
        # Mock embeddings
        mock_embeddings = Mock()
        MockEmbeddings.return_value = mock_embeddings
        
        # Mock Chroma
        mock_chroma = Mock()
        MockChroma.from_documents.return_value = mock_chroma
        
        # Run rebuild
        rebuild_database(str(md_dir), str(db_dir))
        
        # Verify loader was called with correct directory
        MockLoader.assert_called_once()
        call_kwargs = MockLoader.call_args[1]
        assert call_kwargs.get('glob') == '**/*.md'


def test_rebuild_database_splits_documents(tmp_path, monkeypatch):
    """Test that rebuild_database splits documents correctly."""
    from app.rebuild_database import rebuild_database
    
    md_dir = tmp_path / "markdown"
    md_dir.mkdir()
    (md_dir / "test.md").write_text("# Test Document\n\n" + "Long content. " * 100)
    
    db_dir = tmp_path / "chroma_db"
    
    with patch('app.rebuild_database.DirectoryLoader') as MockLoader, \
         patch('app.rebuild_database.Chroma') as MockChroma, \
         patch('app.rebuild_database.HuggingFaceEmbeddings') as MockEmbeddings, \
         patch('app.rebuild_database.RecursiveCharacterTextSplitter') as MockSplitter:
        
        # Mock loader
        mock_loader = Mock()
        mock_doc = Mock()
        mock_doc.page_content = "# Test Document\n\n" + "Long content. " * 100
        mock_doc.metadata = {"source": str(md_dir / "test.md")}
        mock_loader.load.return_value = [mock_doc]
        MockLoader.return_value = mock_loader
        
        # Mock splitter - should split into chunks
        mock_splitter = Mock()
        chunk1 = Mock()
        chunk1.page_content = "Chunk 1"
        chunk1.metadata = mock_doc.metadata
        chunk2 = Mock()
        chunk2.page_content = "Chunk 2"
        chunk2.metadata = mock_doc.metadata
        mock_splitter.split_documents.return_value = [chunk1, chunk2]
        MockSplitter.return_value = mock_splitter
        
        # Mock embeddings
        mock_embeddings = Mock()
        MockEmbeddings.return_value = mock_embeddings
        
        # Mock Chroma
        mock_chroma = Mock()
        MockChroma.from_documents.return_value = mock_chroma
        
        # Run rebuild
        rebuild_database(str(md_dir), str(db_dir))
        
        # Verify splitter was called with correct parameters
        MockSplitter.assert_called_once()
        call_kwargs = MockSplitter.call_args[1]
        assert call_kwargs.get('chunk_size') == 2000
        assert call_kwargs.get('chunk_overlap') == 300

