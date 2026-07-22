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
# Exact User Specification Regex:
# Fluid Code: [A-Z]{1,3} (1-3 letters)
# Line Size: [0-9]{1,2} (1-2 digits)
# Sequence No: [0-9]{3,5} (3-5 digits)
# Pipe Class: [0-9]{3,6}[A-Z]{1,2} (3-6 digits + 1-2 letters)
# Insulation: [A-Z]{1,2} (1-2 letters, optional)
# Format: FluidCode-LineSize-SequenceNo-PipeClass[-Insulation]
LINE_TAG_REGEX = re.compile(
    r'\b[A-Z]{1,3}[-_\s]+[0-9]{1,2}[-_\s]+[0-9]{3,5}[-_\s]+[0-9]{3,6}[A-Z]{1,2}(?:[-_\s]+[A-Z]{1,2})?\b',
    re.IGNORECASE
)

# Broad Fallback Regex matching order variations of the same specification
FALLBACK_LINE_REGEX = re.compile(
    r'\b(?:[A-Z]{1,3}|\d{1,2})[-_\s]+(?:[A-Z]{1,3}|\d{1,2})[-_\s]+[0-9]{3,5}[-_\s]+[0-9]{3,6}[A-Z]{1,2}(?:[-_\s]+[A-Z]{1,2})?\b',
    re.IGNORECASE
)

def extract_text_and_lines_from_pdf(pdf_path: str) -> dict:
    """
    Extract text from a PDF file using PyMuPDF (fitz) and identify P&ID line numbers strictly following format.
    """
    doc = fitz.open(pdf_path)
    lines_found = []
    seen_tags = set()
    page_details = []

    for page_num in range(len(doc)):
        page = doc[page_num]
        text = page.get_text("text")

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
    Strict Parser:
    Fluid Code: [A-Z]{1,3}
    Line Size: [0-9]{1,2}
    Sequence No: [0-9]{3,5}
    Pipe Class: [0-9]{3,6}[A-Z]{1,2}
    Insulation: [A-Z]{1,2} (optional)
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

    if len(parts) >= 4:
        # Standard: FluidCode-LineSize-SequenceNo-PipeClass[-Insulation]
        if re.match(r'^[A-Za-z]{1,3}$', parts[0]) and re.match(r'^\d{1,2}$', parts[1]):
            result["Fluid Code"]     = parts[0]
            result["Line Size (mm)"] = parts[1]
            result["Sequence No"]    = parts[2]
            result["Pipe Class"]     = parts[3]
            if len(parts) > 4:
                result["Insulation"] = parts[4]
        # Reordered: LineSize-FluidCode-SequenceNo-PipeClass[-Insulation]
        elif re.match(r'^\d{1,2}$', parts[0]) and re.match(r'^[A-Za-z]{1,3}$', parts[1]):
            result["Line Size (mm)"] = parts[0]
            result["Fluid Code"]     = parts[1]
            result["Sequence No"]    = parts[2]
            result["Pipe Class"]     = parts[3]
            if len(parts) > 4:
                result["Insulation"] = parts[4]
        else:
            # Match components dynamically by regex
            fluid_part = next((p for p in parts if re.match(r'^[A-Za-z]{1,3}$', p, re.IGNORECASE)), "")
            size_part  = next((p for p in parts if re.match(r'^\d{1,2}$', p)), "")
            seq_part   = next((p for p in parts if re.match(r'^\d{3,5}$', p) and p != size_part), "")
            class_part = next((p for p in parts if re.match(r'^\d{3,6}[A-Za-z]{1,2}$', p, re.IGNORECASE)), "")
            ins_part   = next((p for p in parts if re.match(r'^[A-Za-z]{1,2}$', p, re.IGNORECASE) and p != fluid_part), "")

            result["Fluid Code"]     = fluid_part or parts[0]
            result["Line Size (mm)"] = size_part  or parts[1]
            result["Sequence No"]    = seq_part   or parts[2]
            result["Pipe Class"]     = class_part or parts[3]
            result["Insulation"]     = ins_part   or (parts[4] if len(parts) > 4 else "")

    # Reconstruct standardized clean LINE tag
    clean_parts = [result["Fluid Code"], result["Line Size (mm)"], result["Sequence No"], result["Pipe Class"], result["Insulation"]]
    reconstructed = "-".join([p for p in clean_parts if p])
    if reconstructed:
        result["LINE"] = reconstructed

    return result
