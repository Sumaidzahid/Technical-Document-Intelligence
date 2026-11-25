from docling.document_converter import DocumentConverter
from docling.datamodel.pipeline_options import PdfPipelineOptions, HeadingHierarchyOptions
from docling.datamodel.base_models import InputFormat
from docling_core.types.doc.labels import DocItemLabel
from docling.document_converter import PdfFormatOption

pdf_path = "C:\\Users\\sumai\\Documents\\TDI\\dataset\\operational amplifiers\\lm324.pdf"

pipeline_options = PdfPipelineOptions()
pipeline_options.do_ocr = False
pipeline_options.do_table_structure = False
pipeline_options.generate_picture_images = False
pipeline_options.generate_page_images = False
pipeline_options.do_code_enrichment = False
pipeline_options.do_formula_enrichment = False
pipeline_options.do_picture_classification = False
pipeline_options.heading_hierarchy_options = HeadingHierarchyOptions(
    enabled=True,
    use_bookmarks=True,
    use_numbering=True,
    use_style=True,
    use_font_style=True,
)
converter = DocumentConverter(format_options={InputFormat.PDF: PdfFormatOption(pipeline_options=pipeline_options)})

result = converter.convert(pdf_path)
document = result.document

for item, level in document.iterate_items():
    if getattr(item, "label", None) == DocItemLabel.SECTION_HEADER:
        print({
            "text": getattr(item, "text", ""),
            "level": level,
            "prov": [
                {
                    "page": p.page_no,
                    "bbox": p.bbox.model_dump() if p.bbox else None
                }
                for p in getattr(item, "prov", [])
            ]
        })
# print(document.export_to_markdown())