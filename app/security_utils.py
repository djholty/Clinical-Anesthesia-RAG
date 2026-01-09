"""
Security utility functions for file handling and input validation.
"""
import os
import re
from pathlib import Path


def sanitize_filename(filename: str) -> str:
    """
    Sanitize filename to prevent path traversal attacks.
    
    Args:
        filename: Original filename from user input.
        
    Returns:
        str: Sanitized filename safe for use in file paths.
        
    Examples:
        >>> sanitize_filename("../../../etc/passwd")
        'etcpasswd'
        >>> sanitize_filename("../../windows\\system32\\config\\sam")
        'windowssystem32configsam'
        >>> sanitize_filename("normal_file.pdf")
        'normal_file.pdf'
    """
    if not filename:
        raise ValueError("Filename cannot be empty")
    
    # Remove directory separators and get basename
    safe_name = os.path.basename(filename)
    
    # Remove any remaining path components (../../, ..\\, etc.)
    safe_name = safe_name.replace('..', '')
    safe_name = safe_name.replace('/', '')
    safe_name = safe_name.replace('\\', '')
    
    # Remove any control characters
    safe_name = re.sub(r'[\x00-\x1f\x7f-\x9f]', '', safe_name)
    
    # Limit length (max filename length on most systems)
    safe_name = safe_name[:255]
    
    # Ensure it's not empty after sanitization
    if not safe_name or safe_name == '.' or safe_name == '..':
        raise ValueError("Invalid filename after sanitization")
    
    return safe_name


def validate_safe_path(base_dir: Path, file_path: Path) -> Path:
    """
    Validate that a file path stays within the base directory.
    
    Args:
        base_dir: Base directory that files should be contained within.
        file_path: Path to validate.
        
    Returns:
        Path: Resolved safe path.
        
    Raises:
        ValueError: If path traversal detected.
    """
    base_dir = base_dir.resolve()
    file_path = base_dir / file_path
    
    try:
        resolved = file_path.resolve()
    except (OSError, ValueError):
        raise ValueError("Invalid file path")
    
    # Check if resolved path is within base directory
    try:
        resolved.relative_to(base_dir)
    except ValueError:
        raise ValueError("Path traversal detected - file path outside allowed directory")
    
    return resolved


# Maximum upload file size (50 MB)
MAX_UPLOAD_SIZE = 50 * 1024 * 1024  # 50 MB in bytes


def validate_file_size(file_size: int, max_size: int = MAX_UPLOAD_SIZE) -> None:
    """
    Validate that file size does not exceed maximum allowed size.
    
    Args:
        file_size: Size of the file in bytes.
        max_size: Maximum allowed size in bytes (default: 50 MB).
        
    Raises:
        ValueError: If file size exceeds maximum.
    """
    if file_size > max_size:
        max_mb = max_size / (1024 * 1024)
        raise ValueError(f"File size ({file_size / (1024 * 1024):.2f} MB) exceeds maximum of {max_mb:.0f} MB")


def validate_pdf_content(file_path: str) -> bool:
    """
    Validate that a file is actually a PDF by attempting to parse it.
    
    Args:
        file_path: Path to the file to validate.
        
    Returns:
        bool: True if file is a valid PDF, False otherwise.
        
    Raises:
        ValueError: If file cannot be read or is not a valid PDF.
    """
    try:
        from pypdf import PdfReader
        
        # Check if file starts with PDF signature
        with open(file_path, 'rb') as f:
            header = f.read(4)
            if header != b'%PDF':
                return False
        
        # Try to parse as PDF using PyPDF
        with open(file_path, 'rb') as f:
            pdf_reader = PdfReader(f)
            # Verify we can access metadata (light validation)
            _ = len(pdf_reader.pages)  # Try to get page count
            
        return True
    except ImportError:
        # If pypdf is not available, fall back to header check only
        try:
            with open(file_path, 'rb') as f:
                header = f.read(4)
                return header == b'%PDF'
        except Exception:
            return False
    except Exception:
        # Any error parsing PDF means it's not valid
        return False

