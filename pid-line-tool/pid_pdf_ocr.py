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
# Regex pattern strictly enforcing user's updated format:
# Fluid Code: 2-5 letters (e.g. CWS, HPS, SOL)
# Line Size: 1-3 digits with optional inch quote or mm (e.g. 2", 50)
# Sequence No: 3-6 digits (e.g. 122090, 100305)
# Pipe Class: 2-6 alphanumeric characters (e.g. A1, B2)
# Insulation: 1-2 letters optional (e.g. H)
# Format: Fluid Code, Line Size - Sequence No - Pipe Class - Insulation (e.g. CWS-2"-122090-A1-H or 122090-2"-CWS-A1-H)
LINE_TAG_REGEX = re.compile(
    r'\b(?:[A-Z]{2,5}[-_\s]+)?(?:\d{1,3}"?|\d{3,6})[-_\s]+(?:[A-Z]{2,5}|\d{1,3}"?|\d{3,6})[-_\s]+[A-Z0-9]{2,6}(?:[-_\s]+[A-Z]{1,2})?\b',
    re.IGNORECASE
)

FALLBACK_LINE_REGEX = re.compile(
    r'\b[A-Za-z0-9"#/]+(?:[-_/.][A-Za-z0-9"#/]+){3,5}\b',
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
    Parse extracted tag string into Fluid Code, Line Size, Sequence No, Pipe Class, Insulation.
    Handles order variations:
    e.g. 122090-2"-CWS-A1-H or CWS-2"-122090-A1-H
    """
    parts = [p.strip() for p in tag.split("-") if p.strip()]
    result = {
        "LINE": tag,
        "Fluid Code": "",
        "Line Size (mm)": "",
        "Sequence No": "",
        "Pipe Class": "",
        "Insulation": ""
    }

    if not parts:
        return result

    # Find segment types dynamically based on rules:
    # Size: e.g. 2", 50, 50mm
    size_part = next((p for p in parts if re.match(r'^\d{1,3}"?$', p)), "")
    # Sequence No: e.g. 122090, 100305 (3-6 digits)
    seq_part  = next((p for p in parts if re.match(r'^\d{3,6}$', p) and p != size_part), "")
    # Fluid Code: e.g. CWS, HPS, SOL (2-5 letters)
    fluid_part= next((p for p in parts if re.match(r'^[A-Za-z]{2,5}$', p)), "")
    # Pipe Class: e.g. A1, B2, 150B2
    class_part= next((p for p in parts if re.match(r'^[A-Za-z0-9]{2,6}$', p) and p not in (size_part, seq_part, fluid_part)), "")

    # Insulation: optional 1-2 letters at end
    ins_part = ""
    if len(parts) >= 4 and parts[-1] not in (size_part, seq_part, fluid_part, class_part) and re.match(r'^[A-Za-z]{1,2}$', parts[-1]):
        ins_part = parts[-1]

    # Assign parsed components
    result["Fluid Code"]     = fluid_part or (parts[0] if len(parts) > 0 else "")
    result["Line Size (mm)"] = size_part  or (parts[1] if len(parts) > 1 else "")
    result["Sequence No"]    = seq_part   or (parts[2] if len(parts) > 2 else "")
    result["Pipe Class"]     = class_part or (parts[3] if len(parts) > 3 else "")
    result["Insulation"]     = ins_part   or (parts[4] if len(parts) > 4 else "")

    # Reconstruct standardized clean LINE tag
    clean_parts = [result["Fluid Code"], result["Line Size (mm)"], result["Sequence No"], result["Pipe Class"], result["Insulation"]]
    reconstructed = "-".join([p for p in clean_parts if p])
    if reconstructed:
        result["LINE"] = reconstructed

    return result
