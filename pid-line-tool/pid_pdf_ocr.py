import re
import fitz  # PyMuPDF

# Regex pattern for line tags: e.g. 50-HPS-120816-A5-H or HPS-120816-50-A5-H or 2"-CWS-1001-A1 etc.
# Standard P&ID Line Number regex matching typical formats
LINE_TAG_REGEX = re.compile(
    r'\b(?:[0-9]{1,4}"?[-_\s]*)?[A-Z]{2,6}[-_\s]+[0-9]{3,8}[-_\s]+[0-9]{1,4}"?[-_\s]+[A-Z0-9]{2,8}(?:[-_\s]+[A-Z0-9]{1,4})?\b',
    re.IGNORECASE
)

# Alternative regex pattern for lines with fluid codes
FALLBACK_LINE_REGEX = re.compile(
    r'\b[A-Z]{2,6}[-_\s]+[0-9]{3,8}[-_\s]+[0-9]{1,4}\b',
    re.IGNORECASE
)

def extract_text_and_lines_from_pdf(pdf_path: str) -> dict:
    """
    Extract text from a PDF file using PyMuPDF (fitz) and identify P&ID line numbers.
    Also parses the line numbers into structured components.
    """
    doc = fitz.open(pdf_path)
    lines_found = []
    seen_tags = set()
    page_details = []

    for page_num in range(len(doc)):
        page = doc[page_num]
        text = page.get_text("text")

        # Search regex matches
        matches = LINE_TAG_REGEX.findall(text)
        if not matches:
            matches = FALLBACK_LINE_REGEX.findall(text)

        page_tags = []
        for raw_tag in matches:
            clean_tag = raw_tag.strip().replace(" ", "")
            if clean_tag not in seen_tags:
                seen_tags.add(clean_tag)
                parsed = parse_extracted_tag(clean_tag)
                parsed["page"] = page_num + 1
                parsed["raw_tag"] = clean_tag
                lines_found.append(parsed)
                page_tags.append(clean_tag)

        page_details.append({
            "page": page_num + 1,
            "text_length": len(text),
            "line_count": len(page_tags),
            "lines": page_tags
        })

    doc.close()
    return {
        "total_pages": len(page_details),
        "total_lines_found": len(lines_found),
        "lines": lines_found,
        "page_details": page_details
    }


def parse_extracted_tag(tag: str) -> dict:
    """
    Parse extracted tag string into fluid code, sequence no, size, class, insulation.
    """
    parts = tag.split("-")
    result = {
        "LINE": tag,
        "Fluid Code": "",
        "Sequence No": "",
        "Line Size (mm)": "",
        "Pipe Class": "",
        "Insulation": ""
    }

    if not parts:
        return result

    # Standard order check: if first part is digits (size), e.g. 50-HPS-120816-A5-H
    if parts[0].isdigit() and len(parts) >= 4:
        result["Line Size (mm)"] = parts[0]
        result["Fluid Code"] = parts[1]
        result["Sequence No"] = parts[2]
        result["Pipe Class"] = parts[3]
        if len(parts) > 4:
            result["Insulation"] = parts[4]
    else:
        # Standard: HPS-120816-50-A5-H
        if len(parts) > 0: result["Fluid Code"] = parts[0]
        if len(parts) > 1: result["Sequence No"] = parts[1]
        if len(parts) > 2: result["Line Size (mm)"] = parts[2]
        if len(parts) > 3: result["Pipe Class"] = parts[3]
        if len(parts) > 4: result["Insulation"] = parts[4]

    return result
