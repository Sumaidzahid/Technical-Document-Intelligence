import json
import pymupdf
from typing import Any
from pathlib import Path

def ext_doc_metadata(doc: pymupdf.Document, pdf_path: Path, category: str, project_root: Path) -> dict[str, Any]:
    """
    Extract document-level metadata from a PDF.
    """

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
        "doc_file_size_bytes": pdf_path.stat().st_size,
        "encryption_status": bool(doc.needs_pass),
    }
    return doc_info

def extract_dataset(dataset_dir: Path,categories: list[str],project_root: Path,debug: bool = False) -> dict[str, Any]:

    total_documents = 0
    failed_documents = 0

    result_path = project_root / "output"

    for category in categories:

        category_dir = dataset_dir / category

        pdf_files = sorted(
            file for file in category_dir.rglob("*")
            if file.is_file() and file.suffix.lower() == ".pdf")

        if debug:
            print(f"\nProcessing category: {category}")

        for pdf_path in pdf_files:
            try:
                with pymupdf.open(pdf_path) as doc:

                    doc_info = ext_doc_metadata(doc,pdf_path,category,project_root)

                    output_path = (result_path / category /f"{pdf_path.stem}_metadata.jsonl")

                    output_path.parent.mkdir(parents=True,exist_ok=True)

                    with output_path.open("w", encoding="utf-8") as output_file:
                        output_file.write(json.dumps(doc_info, ensure_ascii=False) + "\n")

                    total_documents += 1

                    if debug:
                        print(f"[OK] {pdf_path.name}")

            except Exception as error:
                failed_documents += 1
                if debug:
                    print(f"[ERROR] {pdf_path.name}: {error}")

    summary = {
        "documents_processed": total_documents,
        "failed_documents": failed_documents,
        "Output_directory" : result_path
    }

    if debug:
        print("\n" + "=" * 50)
        print("DOCUMENT INGESTION SUMMARY")
        print("=" * 50)

        for key, value in summary.items():
            print(f"{key.replace('_', ' ').title()}: {value}")
        print("=" * 50)

    return summary