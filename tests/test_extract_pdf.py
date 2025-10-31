"""
Tests for PDF extraction functions.
"""
import os
import pytest
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock


@pytest.fixture(autouse=True)
def set_env(tmp_path, monkeypatch):
    """Set up environment variables for testing."""
    monkeypatch.setenv("OPENAI_API_KEY", "test_key")
    monkeypatch.setenv("MD_OUTPUT_DIR", str(tmp_path / "output"))
    monkeypatch.setenv("TABLE_CONCURRENCY", "5")
    monkeypatch.setenv("TABLE_DELAY_SECONDS", "0")


def test_check_markdown_exists_true(tmp_path, monkeypatch):
    """Test check_markdown_exists returns True when markdown exists."""
    # Need to reload module to pick up new env vars
    import importlib
    import sys
    if 'app.extract_pdf_to_markdown' in sys.modules:
        importlib.reload(sys.modules['app.extract_pdf_to_markdown'])
    
    from app.extract_pdf_to_markdown import check_markdown_exists
    
    # Set up test directories
    output_dir = tmp_path / "output"
    output_dir.mkdir()
    
    pdf_path = tmp_path / "test.pdf"
    pdf_path.write_bytes(b"%PDF fake")
    
    # Create corresponding markdown file
    md_file = output_dir / "test.md"
    md_file.write_text("# Test\n\nContent")
    
    # Mock the MD_OUTPUT_DIR in the module
    import app.extract_pdf_to_markdown as pdf_extract
    monkeypatch.setattr(pdf_extract, "MD_OUTPUT_DIR", str(output_dir))
    
    result = check_markdown_exists(str(pdf_path))
    assert result is True


def test_check_markdown_exists_false(tmp_path, monkeypatch):
    """Test check_markdown_exists returns False when markdown doesn't exist."""
    import importlib
    import sys
    if 'app.extract_pdf_to_markdown' in sys.modules:
        importlib.reload(sys.modules['app.extract_pdf_to_markdown'])
    
    from app.extract_pdf_to_markdown import check_markdown_exists
    
    output_dir = tmp_path / "output"
    output_dir.mkdir()
    
    pdf_path = tmp_path / "test.pdf"
    pdf_path.write_bytes(b"%PDF fake")
    
    # Don't create markdown file
    
    import app.extract_pdf_to_markdown as pdf_extract
    monkeypatch.setattr(pdf_extract, "MD_OUTPUT_DIR", str(output_dir))
    
    result = check_markdown_exists(str(pdf_path))
    assert result is False


def test_process_single_table_success(monkeypatch):
    """Test process_single_table successfully processes a table."""
    from app.extract_pdf_to_markdown import process_single_table
    
    table_data = [
        ["Header1", "Header2"],
        ["Value1", "Value2"]
    ]
    metadata = {"page_number": 1, "confidence": 0.95}
    
    with patch('app.extract_pdf_to_markdown.reconstruct_table') as mock_reconstruct:
        mock_reconstruct.return_value = "| Header1 | Header2 |\n| Value1 | Value2 |"
        
        result_idx, result_md = process_single_table(table_data, metadata, 0, 1)
        
        assert result_idx == 0
        assert "Header1" in result_md
        mock_reconstruct.assert_called_once()


def test_process_single_table_error_handling(monkeypatch):
    """Test process_single_table handles errors gracefully."""
    from app.extract_pdf_to_markdown import process_single_table
    
    table_data = [["Header", "Value"]]
    metadata = {"page_number": 1}
    
    with patch('app.extract_pdf_to_markdown.reconstruct_table') as mock_reconstruct:
        mock_reconstruct.side_effect = Exception("API error")
        
        result_idx, result_md = process_single_table(table_data, metadata, 0, 1)
        
        assert result_idx == 0
        assert "ERROR" in result_md
        assert "table 1" in result_md

