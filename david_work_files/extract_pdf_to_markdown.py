# ===============================================
# Hybrid PDF → Markdown Converter (Docling + LLM)
# ===============================================

# 1. Install dependencies (uncomment if needed)
#!pip install docling openai tqdm tenacity

import os, json, time, sys, argparse
from tqdm import tqdm
from openai import OpenAI
from tenacity import retry, wait_random_exponential, stop_after_attempt
from docling.document_converter import DocumentConverter
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Initialize clients
client = OpenAI()  # now uses OPENAI_API_KEY from .env file
converter = DocumentConverter()

def find_table_title_in_text(doc_dict, table_el, table_index):
    """Find table title by looking for TABLE X.X patterns in nearby text"""
    texts = doc_dict.get("texts", [])
    
    # Get table page number
    table_page = None
    if "prov" in table_el and table_el["prov"]:
        table_page = table_el["prov"][0].get("page_no")
    
    # Collect all potential table titles with their positions
    potential_titles = []
    for i, text_el in enumerate(texts):
        text_content = text_el.get("text", "").strip()
        text_page = text_el.get("page_number")
        
        # Look for table title patterns (generic approach)
        if "TABLE" in text_content.upper():
            # Make sure it's actually a table title, not just text containing "TABLE"
            if len(text_content) < 200 and "TABLE" in text_content[:20]:
                potential_titles.append((text_content, text_page, i))
    
    # Sort titles by their position in the document
    potential_titles.sort(key=lambda x: x[2])
    
    # Try to match by page number first
    if potential_titles and table_page:
        for title, title_page, pos in potential_titles:
            if title_page == table_page:
                return title
    
    # If no page match, use table index to select appropriate title
    # This assumes tables appear in the same order as their titles in the document
    
    # Fallback: use table index to select appropriate title
    if potential_titles and table_index < len(potential_titles):
        return potential_titles[table_index][0]
    
    return ""

# ---- Step 3: Define the LLM helper for tables ----
@retry(wait=wait_random_exponential(min=2, max=60), stop=stop_after_attempt(10))
def reconstruct_table(table_data, metadata, table_title=""):
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

    Output format:
    1. Table title (if provided): **{table_title}** (on its own line)
    2. Empty line
    3. Markdown table
    4. Optional caption line

    If no table title is provided, just output the Markdown table.
    """

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": prompt}],
        temperature=0
    )

    md_table = response.choices[0].message.content.strip()
    meta = f"<!-- PAGE={page} CONFIDENCE={conf} BBOX={bbox} -->"
    return f"{meta}\n{md_table}"

def convert_pdf_to_markdown(pdf_path, md_path):
    """Convert PDF to Markdown using Docling + OpenAI"""
    
    # ---- Configuration ----
    base = os.path.splitext(os.path.basename(pdf_path))[0]

    # ---- Step 1: Parse the PDF ----
    doc = converter.convert(pdf_path)
    doc_dict = doc.document.model_dump()

    # Optionally save the raw Docling JSON
    with open(f"{base}_docling.json", "w") as f:
        json.dump(doc_dict, f, indent=2)

    # ---- Step 4: Extract text and tables ----
    output_md = []

    # Process texts (paragraphs)
    if "texts" in doc_dict and doc_dict["texts"]:
        print(f"Processing {len(doc_dict['texts'])} text elements...")
        for text_el in tqdm(doc_dict["texts"], desc="Processing texts"):
            page = text_el.get("page_number", "?")
            content = text_el.get("text", "")
            if content.strip():
                meta = f"<!-- PAGE={page} -->"
                output_md.append(meta + "\n" + content)

    # Process tables one at a time with longer delays
    if "tables" in doc_dict and doc_dict["tables"]:
        print(f"Processing {len(doc_dict['tables'])} tables one at a time...")
        for i, table_el in enumerate(doc_dict["tables"]):
            print(f"\n🔄 Processing table {i+1}/{len(doc_dict['tables'])}...")
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
                        print(f"   Table {i+1} has {len(table_data)} rows x {len(table_data[0]) if table_data else 0} columns")
                        
                        # Get table caption/title
                        table_title = ""
                        captions = table_el.get("captions", [])
                        if captions:
                            # Look for the caption text in the texts section
                            for caption_ref in captions:
                                caption_cref = caption_ref.get("cref", "")
                                if caption_cref.startswith("#/texts/"):
                                    text_idx = int(caption_cref.split("/")[-1])
                                    if text_idx < len(doc_dict.get("texts", [])):
                                        caption_text = doc_dict["texts"][text_idx].get("text", "")
                                        if caption_text.strip():
                                            table_title = caption_text.strip()
                                            break
                        
                        # If no caption found, try to find table title in nearby text
                        if not table_title:
                            # Look for table titles in the text elements that appear before this table
                            # This is a more universal approach that works for any PDF
                            table_title = find_table_title_in_text(doc_dict, table_el, i)
                        
                        # Process table with title (LLM will include the title in output)
                        md_table = reconstruct_table(table_data, table_el, table_title)
                        output_md.append(md_table)
                        print(f"   Table {i+1} processed successfully")
                        
                        # Longer delay between tables to avoid rate limiting
                        if i < len(doc_dict["tables"]) - 1:  # Don't delay after the last table
                            print(f"   ⏳ Waiting 1 seconds before next table...")
                            time.sleep(1)
            except Exception as e:
                print(f"   Error processing table {i+1}: {e}")
                output_md.append(f"<!-- ERROR reconstructing table {i+1}: {e} -->")

    # ---- Step 5: Combine and save Markdown ----
    final_markdown = "\n\n".join(output_md)

    with open(md_path, "w") as f:
        f.write(final_markdown)

    print(f"Markdown file saved: {md_path}")
    print(f"Source PDF: {pdf_path}")
    print(f"Raw Docling JSON: {base}_docling.json")

def main():
    parser = argparse.ArgumentParser(description='Convert PDF to Markdown using Docling + OpenAI')
    parser.add_argument('--input', '-i', help='Input PDF file path')
    parser.add_argument('--output', '-o', help='Output markdown file path')
    
    args = parser.parse_args()
    
    if args.input and args.output:
        # Use command line arguments
        pdf_path = args.input
        md_path = args.output
    else:
        # Use default files (for backward compatibility)
        pdf_path = "06_Stoelting.pdf"
        md_path = "06_Stoelting.md"
    
    if not os.path.exists(pdf_path):
        print(f"Error: PDF file not found: {pdf_path}")
        sys.exit(1)
    
    # Create output directory if it doesn't exist
    output_dir = os.path.dirname(md_path)
    if output_dir and not os.path.exists(output_dir):
        os.makedirs(output_dir)
    
    # Run the conversion
    convert_pdf_to_markdown(pdf_path, md_path)

if __name__ == "__main__":
    main()