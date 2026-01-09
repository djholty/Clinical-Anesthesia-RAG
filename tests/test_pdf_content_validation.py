"""
Tests for PDF content validation.
"""
import pytest
import tempfile
from pathlib import Path
from app.security_utils import validate_pdf_content


def test_validate_pdf_content_valid_pdf(tmp_path):
    """Test that valid PDFs pass validation."""
    # Create a proper minimal PDF using pypdf
    try:
        from pypdf import PdfWriter
        from io import BytesIO
        
        # Create a minimal PDF with one blank page
        writer = PdfWriter()
        writer.add_blank_page(width=200, height=200)
        
        buffer = BytesIO()
        writer.write(buffer)
        pdf_bytes = buffer.getvalue()
        
        pdf_file = tmp_path / "test.pdf"
        pdf_file.write_bytes(pdf_bytes)
        
        assert validate_pdf_content(str(pdf_file)) == True
    except ImportError:
        # Skip test if pypdf not available
        pytest.skip("pypdf not available")


def test_validate_pdf_content_invalid_file(tmp_path):
    """Test that non-PDF files fail validation."""
    # Create a fake file with .pdf extension but not a PDF
    fake_pdf = tmp_path / "fake.pdf"
    fake_pdf.write_text("This is not a PDF file")
    
    assert validate_pdf_content(str(fake_pdf)) == False


def test_validate_pdf_content_binary_file(tmp_path):
    """Test that binary files that aren't PDFs fail validation."""
    # Create a binary file that looks like PDF but isn't
    binary_file = tmp_path / "binary.pdf"
    binary_file.write_bytes(b"\x00\x01\x02\x03\x04\x05\x06\x07\x08")
    
    assert validate_pdf_content(str(binary_file)) == False


def test_validate_pdf_content_empty_file(tmp_path):
    """Test that empty files fail validation."""
    empty_file = tmp_path / "empty.pdf"
    empty_file.write_bytes(b"")
    
    assert validate_pdf_content(str(empty_file)) == False


def test_validate_pdf_content_text_file_with_pdf_extension(tmp_path):
    """Test that text files with .pdf extension fail validation."""
    text_file = tmp_path / "text.pdf"
    text_file.write_text("This is a text file with .pdf extension")
    
    assert validate_pdf_content(str(text_file)) == False


def test_validate_pdf_content_nonexistent_file():
    """Test that nonexistent files return False."""
    assert validate_pdf_content("/nonexistent/file.pdf") == False

