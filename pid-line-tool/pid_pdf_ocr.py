import re
import fitz  # PyMuPDF

# Regex pattern for line tags: e.g. 50-HPS-120816-A5-H or HPS-120816-50-A5-H or 2"-CWS-1001-A1 etc.
# Standard P&ID Line Number regex matching typical formats
# Regex pattern strictly enforcing user's philosophy:
# Area: [0-9]{2,3}
# Line Size: [0-9]{1,2}
# Fluid Code: [A-Z]{1,2}
# Sequence No: [0-9]{3,6}
# Pipe Class: [0-9]{3,6}[A-Z]{1,2}
# Insulation: [A-Z]{1,2} (optional)
# e.g., 101-50-SOL-100305-150B2-H or 12-50-FW-120816-300A1
LINE_TAG_REGEX = re.compile(
    r'\b[0-9]{2,3}[-_\s]+[0-9]{1,2}[-_\s]+[A-Z]{1,2}[-_\s]+[0-9]{3,6}[-_\s]+[0-9]{3,6}[A-Z]{1,2}(?:[-_\s]+[A-Z]{1,2})?\b',
    re.IGNORECASE
)

# Broad fallback pattern if space separated or slightly loose
FALLBACK_LINE_REGEX = re.compile(
    r'\b[0-9]{2,3}[-_\s]+[0-9]{1,2}[-_\s]+[A-Z]{1,2}[-_\s]+[0-9]{3,6}[-_\s]+[A-Z0-9]{4,8}\b',
    re.IGNORECASE
)

def extract_text_and_lines_from_pdf(pdf_path: str) -> dict:
    """
    Extract text from a PDF file using PyMuPDF (fitz) and identify P&ID line numbers.
    Also parses the line numbers into structured components strictly following philosophy.
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
    Parse extracted tag string into Area, Line Size, Fluid Code, Sequence No, Pipe Class, Insulation
    strictly adhering to: Area-Size-Fluid-Seq-Class-Insulation.
    """
    parts = tag.split("-")
    result = {
        "LINE": tag,
        "Area": "",
        "Line Size (mm)": "",
        "Fluid Code": "",
        "Sequence No": "",
        "Pipe Class": "",
        "Insulation": ""
    }

    if len(parts) >= 5:
        result["Area"]           = parts[0]
        result["Line Size (mm)"] = parts[1]
        result["Fluid Code"]     = parts[2]
        result["Sequence No"]    = parts[3]
        result["Pipe Class"]     = parts[4]
        if len(parts) > 5:
            result["Insulation"] = parts[5]
    elif len(parts) == 4:
        # If no Area prefix, e.g. 50-SOL-100305-150B2
        if parts[0].isdigit():
            result["Line Size (mm)"] = parts[0]
            result["Fluid Code"]     = parts[1]
            result["Sequence No"]    = parts[2]
            result["Pipe Class"]     = parts[3]
        else:
            result["Fluid Code"]     = parts[0]
            result["Sequence No"]    = parts[1]
            result["Line Size (mm)"] = parts[2]
            result["Pipe Class"]     = parts[3]

    return result
