from typing import Any
from pathlib import Path
import pymupdf
import json
import re

def extract_pdf_pages(pdf_path: Path, category: str, project_root: Path) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """
    Extract text from a PDF, preserving individual page references.
    Returns one record per page.
    """
    records: list[dict[str, Any]] = []
    file_size_bytes = pdf_path.stat().st_size
    with pymupdf.open(pdf_path) as doc:
        metadata = doc.metadata or {}
        doc_info: dict[str, Any] = {
                "record_type": "document",
                "document": pdf_path.name,
                "category": category,
                "source_path": str(pdf_path.relative_to(project_root)),
                "document_title": metadata.get("title"),
                "document_author": metadata.get("author"),
                "creation_date": metadata.get("creationDate"),
                "doc_file_size_bytes": file_size_bytes,
                "encryption_status": bool(doc.needs_pass),
            }
        for page in doc:
            page_number = page.number + 1  # type: ignore 
            text = page.get_text()
            cleaned_text = text.strip() if isinstance(text, str) else ""
            record = {
                    "record_type": "page",
                    "page_number": page_number,
                    "document": pdf_path.name,
                    "category": category,
                    "source_path": doc_info["source_path"],
                    "text_available": bool(cleaned_text),
                    "text_character_count": len(text),
                    "text": text,
                    } 
            records.append(record)
    return records, doc_info

def clean_cell(value: str | None) -> str:
    """Normalise whitespace in an extracted table cell."""
    if value is None:
        return ""

    return re.sub(r"\s+", " ", str(value)).strip()

def table_extractor(pdf_path: Path, debug_t: bool = False) -> list[dict[str, Any]]:
    records_t: list[dict[str, Any]] = []
    with pymupdf.open(pdf_path) as pdf:
        for page_index in range(pdf.page_count):
            page_num = page_index + 1
            page = pdf.load_page(page_index)
            f_tables = page.find_tables()
            assert f_tables is not None
            for table_index, table in enumerate(f_tables.tables, start=1):
                try:
                    rows = table.extract()
                    if debug_t:
                        print(f"Found table on page {page_num}")
                    
                    cleaned_rows = [
                            [clean_cell(cell) for cell in row]
                            for row in rows
                        ]
                    if not any(any(cell for cell in row) for row in cleaned_rows):
                        continue
                        
                    record_t = {
                        "record_type": "table",
                        "document": pdf_path.name,
                        "page_number": page_num,
                        "table_index": table_index,
                        "rows": cleaned_rows,
                    }
                    records_t.append(record_t)
                except Exception as exc:
                    print(
                        f"Table extraction failed: "
                        f"{pdf_path.name}, page {page_num}: {exc}"
                    )
    return records_t
    
def extract_dataset(dataset_dir: Path, categories: list, project_root: Path, debug: bool = False, debug_t: bool = False) -> dict[str, Any]:
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

    result_path = project_root / "output"
    for category in categories:
        category_dir = dataset_dir / category
        pdf_files = sorted(
            file for file in category_dir.rglob("*")
            if file.is_file() and file.suffix.lower() == ".pdf")
        print(f"\nExtracting category: {category}")

        for pdf_path in pdf_files:
            records, doc_info = extract_pdf_pages(pdf_path,category,project_root)
            records_t = table_extractor(pdf_path,debug_t=debug_t)

            text_output_path = result_path / category / f"{pdf_path.stem}_extracted.jsonl"
            table_output_path = (result_path / category / f"{pdf_path.stem}_tables.jsonl")
            try:
                text_output_path.parent.mkdir(parents=True, exist_ok=True)
                table_output_path.parent.mkdir(parents=True, exist_ok=True)
                
                with text_output_path.open("w", encoding="utf-8") as output_file:
                    output_file.write(json.dumps(doc_info, ensure_ascii=False) + "\n")
                    for record in records:
                        output_file.write(json.dumps(record, ensure_ascii=False) + "\n")
                
                with table_output_path.open("w", encoding="utf-8") as output_file:     
                    for record_t in records_t:
                        output_file.write(json.dumps(record_t, ensure_ascii=False) + "\n")
                
                total_tables += len(records_t)

                if records_t:
                    documents_with_tables += 1
                    pages_with_tables += len({
                        record["page_number"] for record in records_t
                    })
                total_documents += 1
                total_pages += len(records)
                pages_with_text += sum(
                record["text_available"] for record in records)
                print(f"[OK] {pdf_path.name}: " 
                    f"{len(records)} pages extracted")
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
    "total_tables": total_tables,
    "documents_with_tables": documents_with_tables,
    "pages_with_tables": pages_with_tables,
    }

    print("\n" + "=" * 50)
    print("TEXT EXTRACTION SUMMARY")
    print("=" * 50)
    for key, value in summary.items():
        print(f"{key.replace('_', ' ').title()}: {value}")
    print(f"Output directory: {result_path}")
    print("=" * 50)

    return summary