import re
import sys
import json
import pymupdf
from collections import Counter
from pathlib import Path
from typing import Any

class NoBookmarks(Exception):
    """Raised when a PDF has no usable bookmark outline."""

def metadata_retrieval(metadata_dir: Path, categories: list) -> list:
    documents = []
    for category in categories:
        category_dir = metadata_dir / category
        jsonl_files = sorted(
            file for file in category_dir.rglob("*")
            if file.is_file() and file.suffix.lower() == ".jsonl")
        for jsonl_file in jsonl_files:
            documents.extend(read_jsonl(jsonl_file))
    return documents

def read_jsonl(jsonl_file: Path) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    with jsonl_file.open("r", encoding="utf-8") as file:
        for line in file:
            if not line.strip():
                continue
            record = json.loads(line)
            if isinstance(record, dict):
                records.append(record)
    return records

MARGIN = 0.081     # top/bottom fraction of the page treated as header/footer zone
REPEAT = 0.40      # a margin line on >= 40% of pages counts as running header/footer

def norm(s: str) -> str:
    """Collapse whitespace, strip leading section number, lowercase."""
    s = " ".join(s.split())
    return re.sub(r"^\d+(?:\.\d+)*\.?\s*", "", s).casefold()

def block_lines(b) -> set[str]:
    """Normalized non-empty lines in a text block."""
    return {
        re.sub(r"\d+", "#", " ".join(line.split()))
        for line in b[4].splitlines()
        if line.strip()
    }

def in_margin(b, page_height: float) -> bool:
    return b[3] < MARGIN * page_height or b[1] > (1 - MARGIN) * page_height

def find_running_blocks(doc: pymupdf.Document) -> set[str]:
    """Keys of header/footer lines that repeat across the document."""
    counts: Counter = Counter()
    for page in doc:
        h = page.rect.height
        keys = {
            key for b in page.get_text("blocks")
            if b[6] == 0 and in_margin(b, h)
            for key in block_lines(b)
        }
        counts.update(keys)
    need = max(3, int(REPEAT * len(doc)))
    return {k for k, c in counts.items() if c >= need}

def locate(blocks: list, title: str) -> int | None:
    """Index of the block whose text is exactly the heading, else None."""
    t = norm(title)
    for i, b in enumerate(blocks):
        if norm(b[4]) == t:
            return i
    return None

def drop_nested(hits: list[int], toc: list) -> list[int]:
    """Remove headings of higher level that sit inside an already-kept heading of lower level (avoids duplicates)."""
    kept: list[int] = []
    for i in hits:
        inside = any(
            h < i and all(toc[m][0] > toc[h][0] for m in range(h + 1, i + 1))
            for h in kept
        )
        if not inside:
            kept.append(i)
    return kept

def section_from_bookmarks(doc: pymupdf.Document, toc: list, idx: int, running: set[str]) -> dict[str, Any]:
    level, title, start_page, *_ = toc[idx]
    # Section ends at the next bookmark of the same or higher level.
    end_idx = next((j for j in range(idx + 1, len(toc)) if toc[j][0] <= level), len(toc))
    end = toc[end_idx] if end_idx < len(toc) else None
    children = [(t[0], t[1], t[2]) for t in toc[idx + 1:end_idx]]
    first = start_page - 1                      # bookmarks are 1-based
    last = max(first, (end[2] - 1) if end else len(doc) - 1)

    pages, warnings = [], []
    for pn in range(first, last + 1):
        h = doc[pn].rect.height
        blocks = [
            b for b in doc[pn].get_text("blocks", sort=True)
            if b[6] == 0 and not (in_margin(b, h) and block_lines(b) & running)
        ]
        lo, hi = 0, len(blocks)

        if pn == first:
            i = locate(blocks, title)
            if i is None:
                warnings.append(f"start anchor not found on page {pn + 1}")
            else:
                lo = i
        if end and pn == last:
            j = locate(blocks, end[1])
            if j is None:
                warnings.append(f"end anchor not found on page {pn + 1}")
            else:
                hi = j

        # Edge case: section starts and ends on the same page
        if hi < lo:
            warnings.append(f"anchors out of order on page {pn + 1}")
            lo, hi = 0, len(blocks)

        text = "\n".join(b[4].strip() for b in blocks[lo:hi]).strip()
        if text:
            pages.append({"page_number": pn + 1, "text": text})

    return {
        "heading": title,
        "bookmark_level": level,
        "start_page": start_page,
        "end_page": last + 1,
        "children": children,
        "text": pages,
        "warnings": warnings,
    }

def sec_ret(pdf_path: Path, search_term: str) -> list[dict[str, Any]]:
    q = norm(search_term)
    with pymupdf.open(pdf_path) as doc:
        toc = [t for t in doc.get_toc() if t[2] > 0]
        if not toc:
            raise NoBookmarks(str(pdf_path))
        hits = [i for i, t in enumerate(toc) if q in norm(t[1])]
        hits = drop_nested(hits, toc)
        running = find_running_blocks(doc)
        return [section_from_bookmarks(doc, toc, i, running) for i in hits]

def summarize(s: dict[str, Any]) -> None:
    n = s["end_page"] - s["start_page"] + 1
    print(f"\n=== {s['heading']} | bookmark level {s['bookmark_level']} "
          f"| pages {s['start_page']}-{s['end_page']} ({n} pages) ===")
    print("Warnings:", "; ".join(s["warnings"]) or "none")
    print("Subsections (from bookmarks):")
    for lvl, title, pg in s["children"]:
        indent = "  " * (lvl - s["bookmark_level"])
        print(f"  {indent}{title}  (p{pg})")
    print("Extracted text per page:")
    for p in s["text"]:
        first_line = p["text"].split("\n", 1)[0][:60]
        print(f"  page: {p['page_number']:>3}  {len(p['text']):>6} chars  starts: {first_line!r}")

def dump_text(s: dict[str, Any]) -> None:
    for p in s["text"]:
        print(f"\n-- Page {p['page_number']} --\n{p['text']}")

if __name__ == "__main__":
    full = "--full" in sys.argv
    project_root = Path(__file__).resolve().parents[2]
    metadata_dir = project_root / "output"
    categories = ["microcontrollers", "operational amplifiers","voltage regulators"]
    
    documents = metadata_retrieval(metadata_dir, categories)
    print(f"\nDocuments retrieved: {len(documents)}")

    target_document = next(
        (d for d in documents if d.get("document", "").lower() == "lm324.pdf"),
        None
    )
    if target_document is None:
        print("LM324 metadata not found.")
        raise SystemExit(1)

    pdf_path = project_root / target_document["source_path"]
    print(f"\nTesting document: {target_document['document']} -> {pdf_path}")

    search_term = "Specifications"
    try:
        sections = sec_ret(pdf_path, search_term)
    except NoBookmarks:
        print("No bookmarks in this PDF; a fallback detector is needed.")
        raise SystemExit(2)
    
    print(f"\nTotal sections retrieved: {len(sections)}")
    for s in sections:
        summarize(s)
        if full:
            dump_text(s)