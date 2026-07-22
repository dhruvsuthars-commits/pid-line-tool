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


def call_anthropic_for_candidates(candidates_page_map: dict[int, list[str]], philosophy: str) -> list[dict]:
    """
    Call Anthropic API (claude-sonnet-4-6) to identify and parse line tags based on line-numbering philosophy.
    """
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise ValueError("ANTHROPIC_API_KEY environment variable is not set. Please configure your API key to use AI Philosophy extraction.")

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
        model="claude-sonnet-4-6",
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

    try:
        results = json.loads(content_clean)
        if not isinstance(results, list):
            results = []
    except Exception as e:
        raise ValueError(f"Failed to parse JSON response from Claude model: {str(e)}. Raw response: {content[:200]}")

    return results


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
