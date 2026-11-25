import re #
import html #
import json
import pymupdf
import pymupdf4llm #
from typing import Any, cast #
from pathlib import Path

def extract_pdf_pages(doc: pymupdf.Document, pdf_path: Path, category: str, project_root: Path) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """
    Extract text from a PDF, preserving individual page references.
    Returns one record per page.
    """
    records: list[dict[str, Any]] = []
    file_size_bytes = pdf_path.stat().st_size

    metadata = doc.metadata or {}
    doc_info: dict[str, Any] = {
        "record_type": "document",
        "document": pdf_path.name,
        "category": category,
        "source_path": str(pdf_path.relative_to(project_root)),
        "document_title": metadata.get("title"),
        "document_author": metadata.get("author"),
        "creation_date": metadata.get("creationDate"),
        "page_count": doc.page_count,
        "doc_file_size_bytes": file_size_bytes,
        "encryption_status": bool(doc.needs_pass),
    }

    # for page in doc:
    #     page_number = page.number + 1  # type: ignore 
    #     text = page.get_text() 
    #     cleaned_text = text.strip() if isinstance(text, str) else ""

    md_pages = cast(list[dict[str, Any]], pymupdf4llm.to_markdown(doc, page_chunks=True))
    for i, chunk in enumerate(md_pages, start=1):
        meta = chunk.get("metadata", {})
        page_number = meta.get("page") or meta.get("page_number") or i
        md_text = chunk.get("text", "")
        cleaned_text = md_text.strip()
        record = {
            "record_type": "page",
            "page_number": page_number,
            "document": pdf_path.name,
            "category": category,
            "source_path": doc_info["source_path"],
            "text_available": bool(cleaned_text),
            "text_character_count": len(md_text),
            "table_count": len(chunk.get("tables", [])),
            "text": md_text,
        } 
        records.append(record)
    return records, doc_info

def is_complex_table(table: Any, rows: list[list[str | None]]) -> tuple[bool, list[str]]:
    """
    Evaluate whether a PyMuPDF table is too complex for standard Markdown.
    Returns (is_complex, list_of_reasons).
    """
    reasons: list[str] = []

    if not rows:
        return False, reasons

    # 1. Check for merged cells 
    if any(cell is None for row in rows for cell in row):
        reasons.append("merged_cells")

    # 2. Check for multi-row headers
    if hasattr(table, "header") and table.header is not None:
        header_rows = [
            r for r in table.rows if r.bbox[3] <= table.header.bbox[3] + 2  # +2pt tolerance
        ]
        if len(header_rows) > 1:
            reasons.append("multi_row_header")

    # 3. Check for multi-line cells or long text blocks inside cells
    has_multiline_or_long_cells = any(
        isinstance(cell, str) and ("\n" in cell.strip() or len(cell.strip()) > 120)
        for row in rows
        for cell in row
    )
    if has_multiline_or_long_cells:
        reasons.append("multiline_or_long_cells")

    # 4. Check for wide tables (> 7 columns)
    max_cols = max(len(row) for row in rows)
    if max_cols > 7:
        reasons.append(f"wide_table_{max_cols}_cols")

    return len(reasons) > 0, reasons

def rows_to_html(rows: list[list[str]]) -> str:
    """[NEW] Helper to convert extracted table rows into clean HTML for complex tables."""
    html_lines = ["<table>"]
    for i, row in enumerate(rows):
        tag = "th" if i == 0 else "td"
        cells = "".join(f"<{tag}>{html.escape(cell)}</{tag}>" for cell in row)
        html_lines.append(f"  <tr>{cells}</tr>")
    html_lines.append("</table>")
    return "\n".join(html_lines)

def clean_cell(value: str | None) -> str:
    """Normalise whitespace in an extracted table cell."""
    if value is None:
        return ""
    return re.sub(r"\s+", " ", str(value)).strip()

def table_extractor(pdf: pymupdf.Document, pdf_path: Path, debug_t: bool = False) -> list[dict[str, Any]]:
    records_t: list[dict[str, Any]] = []
    for page_index in range(pdf.page_count):
        page_num = page_index + 1
        page = pdf.load_page(page_index)
        f_tables = page.find_tables()

        if f_tables is None or not f_tables.tables:
            continue

        for table_index, table in enumerate(f_tables.tables, start=1):
            try:
                rows = table.extract()

                complex_flag, complexity_reasons = is_complex_table(table, rows)
                if not complex_flag: continue # don't recreate simple tables.
                
                if debug_t:
                    print(f"Complex table Found on page {page_num}; Reasons{len(complexity_reasons)}: {complexity_reasons}")

                cleaned_rows = [[clean_cell(cell) for cell in row] for row in rows]
                
                if not any(any(cell for cell in row) for row in cleaned_rows): continue
                    
                record_t = {
                    "record_type": "table",
                    "document": pdf_path.name,
                    "page_number": page_num,
                    "table_index": table_index,
                    "rows":  rows_to_html(cleaned_rows),
                }
                records_t.append(record_t)

            except Exception as exc:
                print(f"Table extraction failed: {pdf_path.name}, page {page_num}: {exc}")
    return records_t
    
def extract_dataset(dataset_dir: Path, categories: list, project_root: Path,h_tables: bool = True, debug: bool = False, debug_t: bool = False) -> dict[str, Any]:
    """
        Extract all PDFs and save page-level records as JSONL.
    """
    total_documents = 0
    total_pages = 0
    pages_with_text = 0
    failed_documents = 0
    total_tables = 0
    documents_with_tables = 0
    pages_with_tables = 0
    mk_table_count = 0
    result_path = project_root / "output"

    for category in categories:
        category_dir = dataset_dir / category
        pdf_files = sorted(
            file for file in category_dir.rglob("*")
            if file.is_file() and file.suffix.lower() == ".pdf")
        print(f"\nExtracting category: {category}")

        for pdf_path in pdf_files:             
            try:
                with pymupdf.open(pdf_path) as doc:
                    records, doc_info = extract_pdf_pages(doc, pdf_path,category,project_root)

                    text_output_path = result_path / category / f"{pdf_path.stem}_extracted.jsonl"
                    text_output_path.parent.mkdir(parents=True, exist_ok=True)

                    with text_output_path.open("w", encoding="utf-8") as output_file:
                        output_file.write(json.dumps(doc_info, ensure_ascii=False) + "\n")
                        for record in records:
                            output_file.write(json.dumps(record, ensure_ascii=False) + "\n")

                    mk_table_count += sum(r["table_count"] for r in records)
                    records_t = []
                    if h_tables:
                        records_t = table_extractor(doc, pdf_path,debug_t=debug_t)
                    pymupdf_table_count = len(records_t)
                    total_tables += pymupdf_table_count
                    if pymupdf_table_count > 0:
                        documents_with_tables += 1
                        pages_with_tables += len({r["page_number"] for r in records_t})

                    if h_tables:
                        table_output_path = (result_path / category / f"{pdf_path.stem}_tables.jsonl")
                        with table_output_path.open("w", encoding="utf-8") as output_file:     
                            for record_t in records_t:
                                output_file.write(json.dumps(record_t, ensure_ascii=False) + "\n")
                    
                    total_documents += 1
                    total_pages += len(records)
                    pages_with_text += sum(record["text_available"] for record in records)
                    print(f"[OK] {pdf_path.name}: {len(records)} pages extracted")
                    
                    if debug:
                        print("Document Level Debugging:")
                        print(f"Title: {doc_info['document_title']}")
                        print(f"Encryption: {doc_info['encryption_status']}")
                        print(f"Category: {doc_info['category']}")
                        print(f"Path: {doc_info['source_path']}")

            except Exception as error:
                failed_documents += 1
                print(f"[ERROR] {pdf_path.name}: {error}")
    summary = {
    "documents_processed": total_documents,
    "failed_documents": failed_documents,
    "total_pages": total_pages,
    "pages_with_text": pages_with_text,
    "pages_without_text": total_pages - pages_with_text,
    "pymupdf_tables_extracted": total_tables,
    "documents_with_tables": documents_with_tables,
    "pages_with_tables": pages_with_tables,
    "markdown_tables_detected": mk_table_count,
    }

    print("\n" + "=" * 50)
    print("TEXT EXTRACTION SUMMARY")
    print("=" * 50)
    for key, value in summary.items():
        print(f"{key.replace('_', ' ').title()}: {value}")
    print(f"Output directory: {result_path}")
    print("=" * 50)

    return summary