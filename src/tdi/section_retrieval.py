import re
import sys
import json
import pymupdf
from collections import Counter
from pathlib import Path
from typing import Any

class NoBookmarks(Exception):
    """Raised when a PDF has no usable bookmark outline."""

#---------------------------loader--------------------------------

def metadata_retrieval(metadata_dir: Path, categories: list) -> list:
    """Retrieve PDF metadata records from the output directory."""
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
    """Read JSON objects from a JSONL file."""
    records: list[dict[str, Any]] = []
    with jsonl_file.open("r", encoding="utf-8") as file:
        for line in file:
            if not line.strip():
                continue
            record = json.loads(line)
            if isinstance(record, dict):
                records.append(record)
    return records

#-------------------------retrieval section------------------------
# Header/footer detection thresholds.
MARGIN = 0.081     # top/bottom fraction of the page treated as header/footer zone
REPEAT = 0.40      # fraction of pages a repeating margin line must appear on

def norm(s: str) -> str:
    """Collapse whitespace, strip leading section number, lowercase."""
    s = " ".join(s.split())
    return re.sub(r"^\d+(?:\.\d+)*\.?\s*", "", s).casefold()

def block_lines(b) -> set[str]:
    """Non-empty lines in a text block, with digits masked for matching."""
    return {
        re.sub(r"\d+", "#", " ".join(line.split()))
        for line in b[4].splitlines()
        if line.strip()
    }

def in_margin(b, page_height: float) -> bool:
    """Return whether a text block intersects the header or footer margin."""
    return b[3] < MARGIN * page_height or b[1] > (1 - MARGIN) * page_height

def find_running_blocks(doc: pymupdf.Document) -> set[str]:
    """Return masked header/footer lines that occur on enough document pages."""
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
    """Remove nested heading hits beneath an already-kept ancestor (avoids duplicates)."""
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
    """Extract the text and bookmark metadata for a searched heading."""
    level, title, start_page, *_ = toc[idx]
    # Section ends at the next bookmark of the same or higher level.
    end_idx = next((j for j in range(idx + 1, len(toc)) if toc[j][0] <= level), len(toc))
    end = toc[end_idx] if end_idx < len(toc) else None
    # child headings that belong to the parent heading
    children = [(t[0], t[1], t[2]) for t in toc[idx + 1:end_idx]]
    
    first = start_page - 1                      # bookmarks are 1-based
    last = max(first, (end[2] - 1) if end else len(doc) - 1) # last page

    pages, warnings = [], []
    start_y = end_y = None # START AND END CORDINATES INTIALIZED
    for pn in range(first, last + 1):
        h = doc[pn].rect.height
        blocks= []
        removed = []
        # Exclude repeated header/footer text while preserving ordinary page text.
        for b in doc[pn].get_text("blocks", sort=True):
            # remove images 6 here is for images
            if b[6] != 0:
                continue
            # if in_margin(b,h) and block_lines(b) & running:
            #     removed.append(b)
            # else:
            #     blocks.append(b)
            # one line version below
            (removed if in_margin(b, h) and block_lines(b) & running else blocks).append(b)
        # Body area: below the running header, above the running footer.
        body_top = max((b[3] for b in removed if b[3] < h / 2), default=0.0)
        body_bottom = min((b[1] for b in removed if b[1] >= h / 2), default=h)
        y_b_t, y_b_b = body_top, body_bottom
        if pn == first:
            i = locate(blocks, title)
            if i is None:
                warnings.append(f"start anchor not found on page {pn + 1}")
            else:
                start_y = blocks[i][1]
                y_b_t = max(y_b_t, start_y) # insure not above in the header and not below bounding box start
        if pn == last:
            # If there is no next heading, set the end boundary to the bottom of the page body (above the footer)
            if end is None:
                end_y = body_bottom
            else:
                j = locate(blocks, end[1])
                if j is None:
                    warnings.append(f"end anchor not found on page {pn + 1}")
                else:
                    end_y = blocks[j][1] 
                    y_b_b = min(y_b_b, end_y) # insure that not below into the footer but above it and not set below the bounding box bottom

        # Edge case: section starts and ends on the same page but in wrong order in that case use the whole page cordinates
        if pn == first == last and start_y is not None and end is not None and end_y is not None and end_y <= start_y:
            warnings.append(f"anchors out of order on page {pn + 1}")
            y_b_t, y_b_b = body_top, body_bottom
            start_y = end_y = None

        if any(y_b_t <= (b[1] + b[3]) / 2 < y_b_b for b in blocks):
            pages.append({"page_number": pn + 1, "y_top": round(y_b_t, 1), "y_bottom": round(y_b_b, 1)})

    return {
        "heading": title,
        "bookmark_level": level,
        "start_page": start_page,
        "end_page": last + 1,
        "start_y": None if start_y is None else round(start_y, 1),
        "end_y": None if end_y is None else round(end_y, 1),
        "pages": pages,
        "children": children,
        "warnings": warnings,
    }

def sec_ret(pdf_path: Path, search_term: str) -> list[dict[str, Any]]:
    """Return bookmark-based section information for headings matching a search term."""
    q = norm(search_term)
    with pymupdf.open(pdf_path) as doc:
        toc = [t for t in doc.get_toc() if t[2] > 0]
        if not toc:
            raise NoBookmarks(str(pdf_path))
        hits = [i for i, t in enumerate(toc) if q in norm(t[1])]
        hits = drop_nested(hits, toc)
        running = find_running_blocks(doc)
        return [section_from_bookmarks(doc, toc, i, running) for i in hits]

# --------------------------------Debug--------------------------------------
def summarize(s: dict[str, Any]) -> None:
    """For debuging and insuring that section retrieval works"""
    n = s["end_page"] - s["start_page"] + 1
    print(f"\n=== {s['heading']} | bookmark level {s['bookmark_level']} "
          f"| pages {s['start_page']}-{s['end_page']} ({n} pages) ===")
    print("Warnings:", "; ".join(s["warnings"]) or "none")
    print("Subsections (from bookmarks):")
    for lvl, title, pg in s["children"]:
        indent = "  " * (lvl - s["bookmark_level"])
        print(f"  {indent}{title}  (p{pg})")
    print("Body band per page (y_top -> y_bottom):")
    for p in s["pages"]:
        print(f"  page: {p['page_number']:>3}  {p['y_top']:>7} -> {p['y_bottom']:>7}")

def section_text(doc: pymupdf.Document, section: dict[str, Any]) -> str:
    """Reference reader: turns a section's bands back into text.
    Whatever consumes the metadata must apply this same rule."""
    out = []
    for p in section["pages"]:
        for b in doc[p["page_number"] - 1].get_text("blocks", sort=True):
            if b[6] == 0 and p["y_top"] <= (b[1] + b[3]) / 2 < p["y_bottom"]:
                out.append(b[4].strip())
    return "\n".join(out)

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
            with pymupdf.open(pdf_path) as doc:
                print("\n" + section_text(doc, s))