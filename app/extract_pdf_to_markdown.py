# ===============================================
# Hybrid PDF → Markdown Converter (Docling + LLM)
# ===============================================

# 1. Install dependencies (uncomment if needed)
#!pip install docling openai tqdm tenacity

import os
import json
import time
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
from tqdm import tqdm
from openai import OpenAI
from tenacity import retry, wait_random_exponential, stop_after_attempt
from docling.document_converter import DocumentConverter
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# ---- Configuration ----
PDF_DIR = "./data/pdfs"
MD_OUTPUT_DIR = "./data/ingested_documents"

# Speed optimization settings
TABLE_CONCURRENCY = int(os.getenv("TABLE_CONCURRENCY", "5"))  # Number of tables to process in parallel
TABLE_DELAY_SECONDS = float(os.getenv("TABLE_DELAY_SECONDS", "0"))  # Delay between table batches (default: 0)

# Initialize clients
openai_api_key = os.getenv("OPENAI_API_KEY")
if not openai_api_key:
    raise ValueError(
        "OPENAI_API_KEY not found in environment variables. "
        "Please set it in your .env file or environment."
    )
client = OpenAI(api_key=openai_api_key)
converter = DocumentConverter()

# ---- Step 2: Define the LLM helper for tables ----
@retry(wait=wait_random_exponential(min=0.5, max=10), stop=stop_after_attempt(10))
def reconstruct_table(table_data, metadata):
    """Use an LLM to rebuild raw table text into Markdown."""
    raw_text = "\n".join(["\t".join(map(str, row)) for row in table_data])
    page = metadata.get("page_number", "?")
    conf = metadata.get("confidence", "?")
    bbox = metadata.get("bbox", "?")

    prompt = f"""
    You are a medical data formatter.
    Convert the following raw table into a valid Markdown table.
    Keep all numeric values and units exactly as-is.
    Do not add or remove data.

    Table (from page {page}, confidence={conf}):
    {raw_text}

    Output ONLY a Markdown table, followed by one or two short caption line.
    """

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": prompt}],
        temperature=0
    )

    md_table = response.choices[0].message.content.strip()
    meta = f"<!-- PAGE={page} CONFIDENCE={conf} BBOX={bbox} -->"
    return f"{meta}\n{md_table}"


def process_single_table(table_data, metadata, table_index, total_tables):
    """
    Process a single table with error handling.
    
    Args:
        table_data: Table data as list of lists.
        metadata: Table metadata.
        table_index: Index of the table (0-based).
        total_tables: Total number of tables.
    
    Returns:
        tuple[int, str]: (table_index, markdown_table) or (table_index, error_message)
    """
    try:
        page = metadata.get("page_number", "?")
        print(f"   🔄 Processing table {table_index + 1}/{total_tables} (page {page})...")
        md_table = reconstruct_table(table_data, metadata)
        print(f"      ✅ Table {table_index + 1} processed successfully")
        return (table_index, md_table)
    except Exception as e:
        error_msg = f"<!-- ERROR reconstructing table {table_index + 1}: {e} -->"
        print(f"      ❌ Error processing table {table_index + 1}: {e}")
        return (table_index, error_msg)


def check_markdown_exists(pdf_path: str) -> bool:
    """
    Check if a markdown version of the PDF already exists.

    Args:
        pdf_path: Path to the PDF file.

    Returns:
        bool: True if markdown file exists, False otherwise.
    """
    pdf_name = Path(pdf_path).stem
    md_file = Path(MD_OUTPUT_DIR) / f"{pdf_name}.md"
    return md_file.exists()


def convert_pdf_to_markdown(pdf_path: str) -> tuple[bool, str]:
    """
    Convert a single PDF file to markdown.

    Args:
        pdf_path: Path to the PDF file to convert.

    Returns:
        tuple[bool, str]: (success, message) indicating conversion result.
    """
    try:
        pdf_path_obj = Path(pdf_path)
        base = pdf_path_obj.stem
        md_path = Path(MD_OUTPUT_DIR) / f"{base}.md"

        print(f"\n📄 Processing: {pdf_path_obj.name}")

        # ---- Step 1: Parse the PDF ----
        doc = converter.convert(str(pdf_path))
        doc_dict = doc.document.model_dump()

        # Optionally save the raw Docling JSON (optional, can be removed if not needed)
        # json_path = Path(MD_OUTPUT_DIR) / f"{base}_docling.json"
        # with open(json_path, "w") as f:
        #     json.dump(doc_dict, f, indent=2)

        # ---- Step 2: Extract text and tables ----
        output_md = []

        # Process texts (paragraphs)
        if "texts" in doc_dict and doc_dict["texts"]:
            print(f"   Processing {len(doc_dict['texts'])} text elements...")
            for text_el in tqdm(doc_dict["texts"], desc="   Processing texts", leave=False):
                page = text_el.get("page_number", "?")
                content = text_el.get("text", "")
                if content.strip():
                    meta = f"<!-- PAGE={page} -->"
                    output_md.append(meta + "\n" + content)

        # Process tables in parallel for speed
        if "tables" in doc_dict and doc_dict["tables"]:
            num_tables = len(doc_dict["tables"])
            print(f"   Processing {num_tables} tables in parallel (concurrency: {TABLE_CONCURRENCY})...")
            
            # Step 1: Extract all table data first (synchronous, fast)
            table_tasks = []
            for i, table_el in enumerate(doc_dict["tables"]):
                try:
                    # Extract table data from new Docling format
                    table_cells = table_el.get("data", {}).get("table_cells", [])
                    if table_cells:
                        # Convert table_cells to the format expected by reconstruct_table
                        table_data = []
                        # Group cells by row
                        rows = {}
                        for cell in table_cells:
                            row_idx = cell.get("start_row_offset_idx", 0)
                            col_idx = cell.get("start_col_offset_idx", 0)
                            text = cell.get("text", "")
                            
                            if row_idx not in rows:
                                rows[row_idx] = {}
                            rows[row_idx][col_idx] = text
                        
                        # Convert to list of lists
                        max_row = max(rows.keys()) if rows else 0
                        for row_idx in range(max_row + 1):
                            if row_idx in rows:
                                max_col = max(rows[row_idx].keys()) if rows[row_idx] else 0
                                row = []
                                for col_idx in range(max_col + 1):
                                    row.append(rows[row_idx].get(col_idx, ""))
                                table_data.append(row)
                        
                        if table_data:
                            print(f"      Table {i+1} has {len(table_data)} rows x {len(table_data[0]) if table_data else 0} columns")
                            table_tasks.append((i, table_data, table_el))
                except Exception as e:
                    print(f"      Error extracting table {i+1} data: {e}")
                    table_tasks.append((i, None, table_el))
            
            # Step 2: Process tables in parallel using ThreadPoolExecutor
            if table_tasks:
                table_results = {}  # Dictionary to store results by index for ordering
                
                with ThreadPoolExecutor(max_workers=TABLE_CONCURRENCY) as executor:
                    # Submit all tasks
                    futures = {}
                    for table_idx, table_data, table_metadata in table_tasks:
                        if table_data:
                            future = executor.submit(
                                process_single_table,
                                table_data,
                                table_metadata,
                                table_idx,
                                num_tables
                            )
                            futures[future] = table_idx
                        else:
                            # Store error for tables that couldn't be extracted
                            table_results[table_idx] = f"<!-- ERROR: Could not extract table {table_idx + 1} data -->"
                    
                    # Collect results as they complete
                    for future in as_completed(futures):
                        table_idx = futures[future]
                        try:
                            idx, result = future.result()
                            table_results[idx] = result
                        except Exception as e:
                            table_results[table_idx] = f"<!-- ERROR processing table {table_idx + 1}: {e} -->"
                
                # Add table results to output in correct order
                for i in range(num_tables):
                    if i in table_results:
                        output_md.append(table_results[i])
                    else:
                        output_md.append(f"<!-- ERROR: Table {i+1} was not processed -->")

        # ---- Step 3: Combine and save Markdown ----
        final_markdown = "\n\n".join(output_md)

        # Ensure output directory exists
        Path(MD_OUTPUT_DIR).mkdir(parents=True, exist_ok=True)

        with open(md_path, "w", encoding="utf-8") as f:
            f.write(final_markdown)

        print(f"   ✅ Markdown file saved: {md_path}")
        return True, f"Successfully converted {pdf_path_obj.name}"

    except KeyboardInterrupt:
        print(f"\n   ⚠️  Conversion interrupted by user for {Path(pdf_path).name}")
        print(f"   ℹ️  No file created - safe to restart")
        raise  # Re-raise to stop processing
    except Exception as e:
        error_msg = f"Error converting {Path(pdf_path).name}: {str(e)}"
        print(f"   ❌ {error_msg}")
        return False, error_msg


def process_pdfs_from_folder():
    """
    Process all PDFs in the PDF_DIR folder that don't have corresponding markdown files.
    """
    pdf_dir = Path(PDF_DIR)
    
    if not pdf_dir.exists():
        print(f"❌ Error: PDF directory not found: {PDF_DIR}")
        return
    
    # Get all PDF files
    pdf_files = list(pdf_dir.glob("*.pdf"))
    
    if not pdf_files:
        print(f"ℹ️  No PDF files found in {PDF_DIR}")
        return
    
    print(f"📚 Found {len(pdf_files)} PDF file(s) in {PDF_DIR}")
    
    # Filter out PDFs that already have markdown versions
    pdfs_to_process = []
    pdfs_skipped = []
    
    for pdf_file in pdf_files:
        if check_markdown_exists(str(pdf_file)):
            pdfs_skipped.append(pdf_file.name)
        else:
            pdfs_to_process.append(pdf_file)
    
    if pdfs_skipped:
        print(f"\n⏭️  Skipping {len(pdfs_skipped)} PDF(s) that already have markdown versions:")
        for name in pdfs_skipped:
            print(f"   - {name}")
    
    if not pdfs_to_process:
        print("\n✅ All PDFs already have markdown versions. Nothing to convert.")
        return
    
    print(f"\n🔄 Processing {len(pdfs_to_process)} PDF(s) that need conversion:")
    
    # Process each PDF
    successful = []
    failed = []
    
    for pdf_file in pdfs_to_process:
        success, message = convert_pdf_to_markdown(str(pdf_file))
        if success:
            successful.append(pdf_file.name)
        else:
            failed.append(pdf_file.name)
    
    # Summary
    print("\n" + "=" * 60)
    print("CONVERSION SUMMARY")
    print("=" * 60)
    print(f"✅ Successfully converted: {len(successful)}")
    if successful:
        for name in successful:
            print(f"   - {name}")
    
    if failed:
        print(f"\n❌ Failed: {len(failed)}")
        for name in failed:
            print(f"   - {name}")
    
    if pdfs_skipped:
        print(f"\n⏭️  Skipped (already exist): {len(pdfs_skipped)}")


if __name__ == "__main__":
    print("=" * 60)
    print("   PDF TO MARKDOWN CONVERTER")
    print("=" * 60)
    process_pdfs_from_folder()
