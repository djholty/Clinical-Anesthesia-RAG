#!/usr/bin/env python3
"""
Batch PDF to Markdown Converter
Converts all PDFs in parent directory and subdirectories to markdown format
"""

import os
import sys
import subprocess
from pathlib import Path
import time

def find_all_pdfs(root_dir):
    """Find all PDF files in the directory tree"""
    pdf_files = []
    for root, dirs, files in os.walk(root_dir):
        for file in files:
            if file.lower().endswith('.pdf'):
                pdf_files.append(os.path.join(root, file))
    return pdf_files

def convert_pdf_to_markdown(pdf_path, output_dir):
    """Convert a single PDF to markdown using the existing script"""
    try:
        # Get the base filename without extension
        base_name = os.path.splitext(os.path.basename(pdf_path))[0]
        
        # Create output filename
        output_file = os.path.join(output_dir, f"{base_name}.md")
        
        print(f"Converting: {os.path.basename(pdf_path)}")
        print(f"Output: {output_file}")
        
        # Run the conversion script
        cmd = [
            sys.executable, 
            "extract_pdf_to_markdown.py",
            "--input", pdf_path,
            "--output", output_file
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True)
        
        if result.returncode == 0:
            print(f"✅ Successfully converted: {base_name}")
            return True
        else:
            print(f"❌ Failed to convert: {base_name}")
            print(f"Error: {result.stderr}")
            return False
            
    except Exception as e:
        print(f"❌ Error converting {pdf_path}: {str(e)}")
        return False

def main():
    # Get the parent directory
    parent_dir = os.path.dirname(os.getcwd())
    rag_ready_dir = os.path.join(parent_dir, "RAG Ready Documents")
    output_dir = os.path.join(rag_ready_dir, "markdown_output")
    
    print(f"🔍 Searching for PDFs in: {rag_ready_dir}")
    print(f"📁 Output directory: {output_dir}")
    print("-" * 60)
    
    # Check if RAG Ready Documents directory exists
    if not os.path.exists(rag_ready_dir):
        print(f"❌ Directory not found: {rag_ready_dir}")
        return
    
    # Find all PDF files in RAG Ready Documents only
    pdf_files = find_all_pdfs(rag_ready_dir)
    
    if not pdf_files:
        print("❌ No PDF files found!")
        return
    
    print(f"📄 Found {len(pdf_files)} PDF files:")
    for pdf in pdf_files:
        print(f"  - {pdf}")
    print("-" * 60)
    
    # Convert each PDF
    successful = 0
    failed = 0
    
    for i, pdf_path in enumerate(pdf_files, 1):
        print(f"\n[{i}/{len(pdf_files)}] Processing: {os.path.basename(pdf_path)}")
        
        if convert_pdf_to_markdown(pdf_path, output_dir):
            successful += 1
        else:
            failed += 1
        
        # Add a small delay to avoid overwhelming the system
        time.sleep(1)
    
    print("\n" + "=" * 60)
    print(f"🎉 Batch conversion completed!")
    print(f"✅ Successful: {successful}")
    print(f"❌ Failed: {failed}")
    print(f"📁 Output directory: {output_dir}")

if __name__ == "__main__":
    main()
