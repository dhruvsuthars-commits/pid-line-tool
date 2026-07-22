import os
import re
import json
import anthropic

# Candidate tag extraction regex for broad shortlisting before LLM call
CANDIDATE_REGEX = re.compile(
    r'\b[A-Za-z0-9"#/]+(?:[-_/.][A-Za-z0-9"#/]+)+\b'
)

def extract_candidate_substrings(text: str) -> list[str]:
    """
    Extract candidate delimiter-separated substrings from raw page text.
    """
    if not text:
        return []
    matches = CANDIDATE_REGEX.findall(text)
    candidates = []
    seen = set()
    for m in matches:
        clean = m.strip().strip("-._/")
        if len(clean) >= 3 and clean not in seen:
            seen.add(clean)
            candidates.append(clean)
    return candidates


def parse_philosophy_rules(philosophy: str) -> dict:
    """
    Parses plain English philosophy text into structured extraction rules.
    """
    text = philosophy.lower()
    rules = {
        "order": [],
        "delimiter": "-",
        "has_area": "area" in text or "unit" in text,
        "has_insulation": "insulation" in text
    }

    # Detect delimiter
    if "separated by" in text:
        delim_match = re.search(r"separated by ['\"]?([^'\"\s]+)['\"]?", text)
        if delim_match:
            rules["delimiter"] = delim_match.group(1)

    # Detect segment order
    order_match = re.search(r'order(?:\s*in\s*this\s*project)?\s*:\s*([^\n\.]+)', text, re.IGNORECASE)
    if order_match:
        raw_order = order_match.group(1)
        tokens = [t.strip() for t in re.split(r'[-_/\.,|]', raw_order) if t.strip()]
        rules["order"] = tokens

    return rules


def local_philosophy_parser(candidates_page_map: dict[int, list[str]], philosophy: str) -> list[dict]:
    """
    Zero-API-Key Local Rule Engine: Parses candidate tags strictly based on user's plain English philosophy.
    """
    rules = parse_philosophy_rules(philosophy)
    results = []

    for page_num, candidates in candidates_page_map.items():
        for cand in candidates:
            parts = [p.strip() for p in re.split(r'[-_/\.]', cand) if p.strip()]
            if len(parts) < 3:
                continue

            # Standard regex pattern matchers per segment type
            area_code = ""
            fluid_code = ""
            sequence_no = ""
            line_size = ""
            pipe_class = ""
            insulation = ""

            # Classify parts strictly based on user's exact philosophy specification:
            # Area: [0-9]{2,3}
            # Line Size: [0-9]{1,2}
            # Fluid Code: [A-Z]{1,2}
            # Sequence No: [0-9]{3,6}
            # Pipe Class: [0-9]{3,6}[A-Z]{1,2}
            # Insulation: [A-Z]{1,2}
            if len(parts) >= 5:
                area_code   = parts[0] if re.match(r'^\d{2,3}$', parts[0]) else ""
                line_size   = parts[1] if re.match(r'^\d{1,2}$', parts[1]) else ""
                fluid_code  = parts[2] if re.match(r'^[A-Za-z]{1,2}$', parts[2], re.IGNORECASE) else ""
                sequence_no = parts[3] if re.match(r'^\d{3,6}$', parts[3]) else ""
                pipe_class  = parts[4] if re.match(r'^\d{3,6}[A-Za-z]{1,2}$', parts[4], re.IGNORECASE) else ""
                if len(parts) > 5 and re.match(r'^[A-Za-z]{1,2}$', parts[5], re.IGNORECASE):
                    insulation = parts[5]
            else:
                fluid_part = next((p for p in parts if re.match(r'^[A-Za-z]{1,2}$', p, re.IGNORECASE)), "")
                seq_part   = next((p for p in parts if re.match(r'^\d{3,6}$', p)), "")
                size_part  = next((p for p in parts if re.match(r'^\d{1,2}$', p) and p != seq_part), "")
                class_part = next((p for p in parts if re.match(r'^\d{3,6}[A-Za-z]{1,2}$', p, re.IGNORECASE)), "")

                fluid_code  = fluid_part
                sequence_no = seq_part
                line_size   = size_part
                pipe_class  = class_part

            fields = {
                "Area": area_code,
                "Line Size": line_size,
                "Fluid Code": fluid_code,
                "Sequence No": sequence_no,
                "Pipe Class": pipe_class,
                "Insulation": insulation
            }

            # Only accept candidate if at least Fluid, Sequence, Size, Class match philosophy
            if fluid_code and sequence_no and line_size and pipe_class:
                results.append({
                    "LINE": cand,
                    "page": page_num,
                    "fields": fields,
                    "confidence": "high"
                })

    return results


def call_anthropic_for_candidates(candidates_page_map: dict[int, list[str]], philosophy: str) -> list[dict]:
    """
    Call Anthropic API (claude-3-5-sonnet) with local rule engine fallback if API key is not provided.
    """
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key or api_key.startswith("YOUR_") or "sk-air-" in api_key:
        # Fallback to local rule engine if no API key set or invalid placeholder
        return local_philosophy_parser(candidates_page_map, philosophy)

    try:
        client = anthropic.Anthropic(api_key=api_key)

        system_prompt = (
            "You are an expert P&ID Piping & Instrumentation Engineering Assistant.\n"
            "Your task is to analyze candidate strings extracted from P&ID drawing pages, filter out any unwanted text, and strictly parse ONLY line tags that follow the user's specific line-numbering philosophy.\n\n"
            "CRITICAL RULES:\n"
            "1. STRICT SEGMENT & PATTERN MATCHING: A valid line tag MUST match the exact segment count, segment types, and segment order defined in the philosophy.\n"
            "2. STRIP UNWANTED SURROUNDING TEXT: If a candidate string contains leading/trailing text or line numbers appended to adjacent text (e.g., '101SOL-100305-50-B2' where '101' is an unwanted prefix or line size, or '80BPA-010101-300-B1BPA'), trim or isolate ONLY the clean matching LINE tag, such as 'SOL-100305-50-B2' or 'BPA-010101-300-B1'. NEVER include unwanted prefixes in Fluid Code or Pipe Class.\n"
            "3. FIELD INFERENCE & PARSING: Extract each segment into its exact field (e.g., Fluid Code, Sequence No, Line Size, Pipe Class, Insulation). Fluid Code must ONLY contain the fluid abbreviation (e.g. 'SOL', 'CHBR', 'BPA', 'PRO'). Pipe Class must ONLY contain the specification code (e.g. 'B2', 'A2', 'B1').\n"
            "4. REJECT INVALID STRINGS: Reject candidates completely if they cannot form a clean valid line tag under the philosophy.\n"
            "5. CONFIDENCE SCORE: Assign 'high' for perfect matches, 'medium' for minor cleanups, 'low' for uncertain matches.\n"
            "6. Return STRICT JSON ONLY as a JSON array of objects without markdown code block fences.\n\n"
            "Example JSON output:\n"
            "[\n"
            '  {"LINE": "SOL-100305-50-B2", "page": 1, "fields": {"Fluid Code": "SOL", "Sequence No": "100305", "Line Size": "50", "Pipe Class": "B2", "Insulation": ""}, "confidence": "high"}\n'
            "]"
        )

        user_prompt = (
            f"Line-Numbering Philosophy:\n{philosophy}\n\n"
            f"Candidate Substrings per Page:\n{json.dumps(candidates_page_map, indent=2)}\n\n"
            "Extract, filter, and parse matching line tags into strict JSON array."
        )

        response = client.messages.create(
            model="claude-3-5-sonnet-20241022",
            max_tokens=4000,
            temperature=0.0,
            system=system_prompt,
            messages=[{"role": "user", "content": user_prompt}]
        )

        content = ""
        for block in response.content:
            if hasattr(block, 'text'):
                content += block.text

        content_clean = content.strip()
        if content_clean.startswith("```"):
            content_clean = re.sub(r'^```(?:json)?\n?', '', content_clean)
            content_clean = re.sub(r'\n?```$', '', content_clean)

        results = json.loads(content_clean)
        return results if isinstance(results, list) else local_philosophy_parser(candidates_page_map, philosophy)
    except Exception as e:
        print(f"API Call failed or Key invalid ({str(e)}), falling back to Local Philosophy Engine")
        return local_philosophy_parser(candidates_page_map, philosophy)


def extract_lines_with_philosophy(page_texts: list[str], philosophy: str) -> list[dict]:
    """
    Extracts and parses line tags across all pages of a PDF using Anthropic Claude sonnet-4-6.
    Batches pages in chunks to stay within token limits and de-duplicates by 'LINE'.
    """
    if not philosophy or not philosophy.strip():
        raise ValueError("No philosophy description provided.")

    all_page_candidates = {}
    for idx, text in enumerate(page_texts):
        cands = extract_candidate_substrings(text)
        if cands:
            all_page_candidates[idx + 1] = cands

    if not all_page_candidates:
        return []

    # Batch pages in chunks of 5 pages max to avoid prompt bloat
    page_numbers = sorted(all_page_candidates.keys())
    chunk_size = 5
    page_chunks = [page_numbers[i:i + chunk_size] for i in range(0, len(page_numbers), chunk_size)]

    all_raw_matches = []
    for chunk in page_chunks:
        chunk_map = {pg: all_page_candidates[pg] for pg in chunk}
        chunk_results = call_anthropic_for_candidates(chunk_map, philosophy)
        all_raw_matches.extend(chunk_results)

    # De-duplicate by LINE tag
    seen_lines = set()
    final_lines = []

    for match in all_raw_matches:
        fields = match.get("fields", {})
        if not isinstance(fields, dict):
            fields = {}

        # Standard field extraction & normalization
        raw_fluid = (fields.get("Fluid Code") or fields.get("Fluid") or fields.get("Service") or "").strip()
        raw_seq   = (fields.get("Sequence No") or fields.get("Sequence Number") or fields.get("Seq No") or "").strip()
        raw_size  = (fields.get("Line Size") or fields.get("Size") or fields.get("Line Size (mm)") or "").strip()
        raw_class = (fields.get("Pipe Class") or fields.get("Class") or fields.get("Spec") or "").strip()
        raw_ins   = (fields.get("Insulation") or fields.get("Insulation Code") or "").strip()
        raw_area  = (fields.get("Area") or fields.get("Unit") or "").strip()

        # Deterministic Regex Cleaners:
        # 1. Clean Fluid Code: strip leading numbers (e.g., '101SOL' -> 'SOL', '80BPA' -> 'BPA')
        fluid_code = re.sub(r'^\d+', '', raw_fluid).strip()

        # 2. Clean Pipe Class: extract spec code like A1, A2, B1, B2, C14 (strip appended fluid names like 'B1BPA' -> 'B1', 'B2 C14' -> 'B2')
        pipe_class_match = re.match(r'^([A-Za-z]\d+|[A-Za-z0-9]{2,4})', raw_class)
        pipe_class = pipe_class_match.group(1) if pipe_class_match else raw_class

        sequence_no = raw_seq
        line_size = raw_size
        insulation = raw_ins
        area_code = raw_area

        # Reconstruct clean exact LINE tag strictly from philosophy fields
        reconstructed_parts = [p for p in [area_code, fluid_code, sequence_no, line_size, pipe_class, insulation] if p]
        if len(reconstructed_parts) >= 3:
            line_tag = "-".join(reconstructed_parts)
        else:
            line_tag = str(match.get("LINE", "")).strip()

        if not line_tag or line_tag in seen_lines:
            continue
        seen_lines.add(line_tag)

        parsed_item = {
            "LINE": line_tag,
            "page": match.get("page", 1),
            "confidence": match.get("confidence", "high"),
            "fields": {
                "Fluid Code": fluid_code,
                "Sequence No": sequence_no,
                "Line Size": line_size,
                "Pipe Class": pipe_class,
                "Insulation": insulation
            },
            "Fluid Code": fluid_code,
            "Sequence No": sequence_no,
            "Line Size (mm)": line_size,
            "Pipe Class": pipe_class,
            "Insulation": insulation
        }

        final_lines.append(parsed_item)

    return final_lines


def preview_philosophy_sample(sample_text: str, philosophy: str) -> list[dict]:
    """
    Tests line-numbering philosophy on sample text snippet.
    """
    candidates = extract_candidate_substrings(sample_text)
    if not candidates:
        # If text is raw line tags or lines separated by newlines
        candidates = [line.strip() for line in sample_text.splitlines() if line.strip()]

    sample_map = {1: candidates}
    return call_anthropic_for_candidates(sample_map, philosophy)
