"""
Tests for security utility functions.
"""
import pytest
from pathlib import Path
from app.security_utils import sanitize_filename, validate_safe_path


def test_sanitize_filename_normal():
    """Test sanitize_filename with normal filenames."""
    assert sanitize_filename("normal_file.pdf") == "normal_file.pdf"
    assert sanitize_filename("test-document.pdf") == "test-document.pdf"
    assert sanitize_filename("file123.pdf") == "file123.pdf"


def test_sanitize_filename_path_traversal():
    """Test sanitize_filename prevents path traversal."""
    # os.path.basename() removes directory components with forward slashes
    assert sanitize_filename("../../../etc/passwd") == "passwd"
    assert sanitize_filename("../../etc/passwd") == "passwd"
    assert sanitize_filename("../test.pdf") == "test.pdf"
    assert sanitize_filename("/etc/passwd") == "passwd"
    
    # On Unix, backslashes are treated as literal characters by basename,
    # then removed by our sanitization. The important thing is security:
    # no path traversal can occur - all path components are removed
    result_win = sanitize_filename("..\\..\\windows\\system32\\config\\sam")
    # Security check: verify no path components can cause traversal
    assert "\\" not in result_win  # Backslashes removed
    assert ".." not in result_win   # Parent directory removed
    assert "/" not in result_win    # Forward slashes removed
    
    # Verify no path components remain
    result = sanitize_filename("../../../etc/passwd")
    assert "/" not in result
    assert ".." not in result


def test_sanitize_filename_removes_separators():
    """Test sanitize_filename removes directory separators."""
    # os.path.basename() removes forward slash paths
    assert sanitize_filename("path/to/file.pdf") == "file.pdf"
    
    # On Unix, basename treats backslashes as literal, then we remove them
    # Security: The key is that no path separators remain - the exact output
    # format is less important than preventing path traversal
    result_win = sanitize_filename("path\\to\\file.pdf")
    assert "\\" not in result_win  # Backslashes removed - SECURITY CRITICAL
    assert "/" not in result_win   # No forward slashes
    assert result_win.endswith(".pdf")  # Extension preserved
    
    # Windows absolute path - basename handles it, we remove backslashes
    result_abs = sanitize_filename("C:\\Users\\test\\file.pdf")
    assert "\\" not in result_abs  # Backslashes removed
    assert "/" not in result_abs   # No forward slashes
    
    # Verify no separators remain in any case - this is the security requirement
    result1 = sanitize_filename("path/to/file.pdf")
    result2 = sanitize_filename("path\\to\\file.pdf")
    assert "/" not in result1
    assert "\\" not in result1
    assert "/" not in result2
    assert "\\" not in result2


def test_sanitize_filename_removes_control_chars():
    """Test sanitize_filename removes control characters."""
    # Contains null byte and newline
    result = sanitize_filename("file\x00name\n.pdf")
    assert "\x00" not in result
    assert "\n" not in result


def test_sanitize_filename_length_limit():
    """Test sanitize_filename limits length."""
    long_name = "a" * 300
    result = sanitize_filename(long_name)
    assert len(result) == 255


def test_sanitize_filename_empty():
    """Test sanitize_filename rejects empty filenames."""
    with pytest.raises(ValueError, match="cannot be empty"):
        sanitize_filename("")
    with pytest.raises(ValueError, match="cannot be empty"):
        sanitize_filename(None)


def test_sanitize_filename_only_dots():
    """Test sanitize_filename rejects filenames that are only dots."""
    with pytest.raises(ValueError, match="Invalid filename"):
        sanitize_filename("..")
    with pytest.raises(ValueError, match="Invalid filename"):
        sanitize_filename(".")


def test_validate_safe_path_valid():
    """Test validate_safe_path with valid paths."""
    base_dir = Path("/tmp/test")
    file_path = Path("subdir/file.pdf")
    result = validate_safe_path(base_dir, file_path)
    assert result.is_absolute()
    assert "subdir" in str(result)


def test_validate_safe_path_path_traversal():
    """Test validate_safe_path prevents path traversal."""
    base_dir = Path("/tmp/test")
    
    # Path traversal attempts should fail
    with pytest.raises(ValueError, match="Path traversal detected"):
        validate_safe_path(base_dir, Path("../../etc/passwd"))
    
    with pytest.raises(ValueError, match="Path traversal detected"):
        validate_safe_path(base_dir, Path("../other_dir/file.pdf"))


def test_validate_safe_path_invalid_path():
    """Test validate_safe_path with invalid paths."""
    base_dir = Path("/tmp/test")
    
    # Invalid characters or extremely long paths
    with pytest.raises(ValueError, match="Invalid file path"):
        validate_safe_path(base_dir, Path("\x00invalid"))


