from pathlib import Path
from typing import Any, cast
import pymupdf
import re
from collections import Counter

pdf_path = Path(r"C:\\Users\\sumai\\Documents\\TDI\\dataset\\operational amplifiers\\lm324.pdf")

with pymupdf.open(pdf_path) as doc:

    for page_num in range(5, 15):
        page = doc[page_num - 1]

        print(f"\n--- PAGE {page_num} ---")

        page_dict = cast(dict[str, Any], page.get_text("dict"))
        for block in page_dict["blocks"]:
            for line in block.get("lines", []):
                for span in line["spans"]:
                    text = span["text"].strip()

                    if text:
                        print(
                            f"{span['size']:.1f} | "
                            f"{span['font']} | "
                            f"{span['flags']} | "
                            f"{text[:100]}"
                        )
                        
with pymupdf.open(pdf_path) as doc:

    for page_num in [5, 6, 7, 8, 45]:

        page = doc[page_num - 1]
        page_dict = cast(dict[str, Any], page.get_text("dict"))

        spans = []

        for block in page_dict["blocks"]:
            for line in block.get("lines", []):
                for span in line["spans"]:
                    spans.append(span)

        print(f"\n{'=' * 60}")
        print(f"PAGE {page_num}")
        print(f"{'=' * 60}")

        # Font size distribution
        font_sizes = Counter(
            round(span["size"], 1) for span in spans
        )

        print("\nFont size distribution:")
        for size, count in sorted(font_sizes.items(), reverse=True):
            print(f"{size} pt: {count} spans")

        # Inspect numbered text spans
        print("\nNumbered text spans:")

        for span in spans:
            text = span["text"].strip()

            if re.match(r"^\d+(?:\.\d+)*\s+", text):
                print(
                    f"Text: {text[:100]}\n"
                    f"Font: {span['font']}\n"
                    f"Size: {span['size']}\n"
                    f"Flags: {span['flags']}\n"
                    f"Position: {span['bbox']}\n"
                )