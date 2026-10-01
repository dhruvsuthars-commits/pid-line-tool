"""
P&ID Line List Segregator
Parses LINE tags and AutoCAD export sheets into Linelist_reference template.
Supports new template column mappings:
  A = Sr. No
  B = Drawing Number (cleaned from Col A filename)
  C = Nominal pipe size mm (Nominal dia)
  D = Service Code (Fluid Code)
  E = Line number (Sequence Number)
  I = Pipe Spec (Pipe Class)
  T = Tracing / Jacketing
  U = Insulation
"""

import re
import os
import json
import pandas as pd
from copy import copy
from openpyxl import load_workbook
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter, column_index_from_string
from openpyxl.cell.cell import MergedCell

TEMPLATE_HEADER_ROW = 5
DATA_START_ROW      = 7

LINE_SOURCE_COL = "LINE"

PARSED_COL_MAP = {
    "Line Size (mm)":  "C",   # Nominal dia -> Column-C
    "Fluid Code":      "D",   # Fluid Code -> Column-D
    "Sequence No":     "E",   # Sequence Number -> Column-E
    "Pipe Class":      "I",   # Pipe Class -> Column-I
    "Tracing":         "T",   # Tracing / Jacketing -> Column-T
    "Insulation":      "U",   # Insulation -> Column-U
}

COL_MAP = {}

ROW_FILL_EVEN = PatternFill("solid", start_color="FFFFFF", end_color="FFFFFF")
ROW_FILL_ODD  = PatternFill("solid", start_color="F2F9F2", end_color="F2F9F2")

THIN = Side(style="thin", color="000000")
DATA_BORDER = Border(left=THIN, right=THIN, top=THIN, bottom=THIN)

STANDARD_FIELD_ALIASES = {
    "Fluid Code":      ["Fluid Code", "Fluid", "Service", "FluidCode"],
    "Sequence No":     ["Sequence No", "Sequence Number", "Seq No", "SeqNo", "Sequence"],
    "Line Size (mm)":  ["Line Size (mm)", "Line Size", "Size", "LineSize", "Nominal Dia", "Nominal pipe size mm"],
    "Pipe Class":      ["Pipe Class", "Class", "Spec", "PipeClass", "Pipe Spec"],
    "Tracing":         ["Tracing", "Tracing / Jacketing", "Jacketing"],
    "Insulation":      ["Insulation", "Insulation Code", "InsulationCode"],
}


def parse_line(line_tag: str) -> dict:
    """
    Parse a LINE tag in format:
      FLUID CODE-SEQUENCE NUMBER-LINE SIZE-PIPE CLASS-[TRACING]-[INSULATION]
    Examples:
      - PVT-210117-100-MS1-IH  -> Fluid: PVT, Seq: 210117, Size: 100, Class: MS1, Ins: IH
      - PR-210127-50-MS1       -> Fluid: PR, Seq: 210127, Size: 50, Class: MS1
      - N2-XXXXX-25-GI         -> Fluid: N2, Seq: XXXXX, Size: 25, Class: GI
      - PR-210137-80-MS1-ET-IH -> Fluid: PR, Seq: 210137, Size: 80, Class: MS1, Tracing: ET, Ins: IH
      - PR-210160-XX-MS1       -> Fluid: PR, Seq: 210160, Size: XX, Class: MS1
    """
    result = {
        "Fluid Code":     "",
        "Sequence No":    "",
        "Line Size (mm)": "",
        "Pipe Class":     "",
        "Tracing":        "",
        "Insulation":     "",
    }

    if not line_tag or str(line_tag).strip() in ("", "nan", "NaN"):
        return result

    raw = str(line_tag).strip()
    parts = [p.strip() for p in raw.split("-") if p.strip() != ""]

    if not parts:
        return result

    # Part 0: Fluid Code (e.g. PVT, PR, N2, CHWR, CA)
    if len(parts) > 0:
        result["Fluid Code"] = parts[0].upper()

    # Part 1: Sequence Number (e.g. 210117, XXXXX, 2101XX)
    if len(parts) > 1:
        result["Sequence No"] = parts[1]

    # Part 2: Line Size (e.g. 100, 50, XX)
    if len(parts) > 2:
        result["Line Size (mm)"] = parts[2]

    # Part 3: Pipe Class (e.g. MS1, GI, CS1)
    if len(parts) > 3:
        result["Pipe Class"] = parts[3].upper()

    # If 5 parts: e.g. PVT-210117-100-MS1-IH or PR-210127-50-MS1-ET
    if len(parts) == 5:
        p4 = parts[4].upper()
        if p4 in ("ET", "ST", "WT", "HT", "SJ", "WJ"):
            result["Tracing"] = p4
        else:
            result["Insulation"] = p4

    # If 6 or more parts: e.g. PR-210137-80-MS1-ET-IH
    elif len(parts) >= 6:
        result["Tracing"] = parts[4].upper()
        result["Insulation"] = parts[5].upper()

    return result


def _write_cell(ws, row: int, col_letter: str, value, fill):
    """Write a styled data cell safely handling MergedCell."""
    col_idx = column_index_from_string(col_letter)
    cell = ws.cell(row=row, column=col_idx)

    if isinstance(cell, MergedCell):
        for rng in ws.merged_cells.ranges:
            if cell.coordinate in rng:
                cell = ws.cell(row=rng.min_row, column=rng.min_col)
                break

    str_val = str(value) if value is not None else ""
    cell.value     = "" if str_val in ("nan", "NaN") else (value if value is not None else "")
    cell.fill      = fill
    cell.border    = DATA_BORDER
    cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=False)
    cell.font      = Font(name="Arial", size=9)


def find_line_column(df: pd.DataFrame) -> str:
    """Find the column in DataFrame containing LINE / Line Number details."""
    cols = list(df.columns)
    
    # 1. Exact or common case-insensitive names
    for target in ["LINE", "LINE NO", "LINE NO.", "LINE NUMBER", "LINENUMBER", "TAG", "LINE_TAG"]:
        match = next((c for c in cols if c.strip().upper() == target), None)
        if match:
            return match

    # 2. Check for any column containing 'LINE'
    for c in cols:
        cu = c.strip().upper()
        if "LINE" in cu and not any(skip in cu for skip in ["SIZE", "SPEC", "CLASS", "DWG", "DRAWING"]):
            return c

    # 3. Content scanning fallback
    for c in cols:
        sample_vals = df[c].dropna().astype(str).head(10).tolist()
        dash_count = sum(1 for v in sample_vals if len(v.split("-")) >= 3)
        if dash_count >= max(2, len(sample_vals) // 2):
            return c

    return cols[1] if len(cols) > 1 else cols[0]


def get_drawing_no(df: pd.DataFrame, row_idx: int) -> str:
    """Extract and clean drawing number from column A / source filename."""
    if len(df.columns) < 1:
        return ""
    col_a_val = str(df.iloc[row_idx, 0]).strip()
    if col_a_val in ("", "nan", "NaN"):
        return ""
    val = os.path.basename(col_a_val)
    if val.lower().endswith(".dwg"):
        val = val[:-4]
    return val


def get_sr_no(df: pd.DataFrame, row_idx: int) -> int:
    """Generate sequential 1-based Serial Number."""
    return row_idx + 1


def get_target_sheet(wb):
    """Find the best target sheet for line list insertion."""
    sheet_names = wb.sheetnames

    # 1. Sheet with 'LINE' in name
    for s in sheet_names:
        if "LINE" in s.strip().upper():
            return wb[s]

    # 2. Sheet with 'PID-' or 'P&ID' or 'FINAL'
    for s in sheet_names:
        su = s.strip().upper()
        if su.startswith("PID-") or "PID" in su or "FINAL" in su:
            return wb[s]

    # 3. Fallback to active sheet
    return wb.active


def get_mn_target_columns(ws) -> tuple:
    """Find columns for Pressure Nor. and Temp Nor."""
    press_col = "O"
    temp_col = "Q"

    for row_idx in (3, 4, 5):
        for cell in ws[row_idx]:
            val = str(cell.value or "").strip().upper()
            if "PRESSURE" in val and ("NOR" in val or "OPERAT" in val):
                press_col = cell.column_letter
            elif "TEMP" in val and ("NOR" in val or "OPERAT" in val):
                temp_col = cell.column_letter

    return press_col, temp_col


def load_input_dataframe(input_path: str) -> pd.DataFrame:
    """Load AutoCAD export Excel sheet, prioritizing sheet 'LINE NUMBER'."""
    xl = pd.ExcelFile(input_path)
    sheet_names = xl.sheet_names

    target_sheet = next(
        (s for s in sheet_names if s.strip().upper() in ("LINE NUMBER", "LINENUMBER", "LINE_NUMBER", "LINE NO")),
        None
    )
    if not target_sheet:
        target_sheet = next(
            (s for s in sheet_names if "LINE" in s.strip().upper()),
            None
        )
    if not target_sheet:
        target_sheet = sheet_names[0]

    return pd.read_excel(input_path, sheet_name=target_sheet)


def get_parsed_df_from_input(df: pd.DataFrame) -> pd.DataFrame:
    """Extract or generate parsed_df from input DataFrame."""
    existing_parsed = {}
    for std_key, aliases in STANDARD_FIELD_ALIASES.items():
        match_col = next((c for c in df.columns if c in aliases or c.strip().lower() in [a.lower() for a in aliases]), None)
        if match_col:
            existing_parsed[std_key] = df[match_col]

    if existing_parsed:
        for std_key in PARSED_COL_MAP.keys():
            if std_key not in existing_parsed:
                existing_parsed[std_key] = [""] * len(df)
        parsed_df = pd.DataFrame(existing_parsed)
        for col in df.columns:
            if col not in [LINE_SOURCE_COL, "Source PDF Name"] and col not in parsed_df.columns:
                parsed_df[col] = df[col]
        return parsed_df
    else:
        line_col = find_line_column(df)
        return pd.DataFrame(df[line_col].apply(parse_line).tolist())


def _apply_mn_rules(parsed_df: pd.DataFrame, configs: list) -> pd.DataFrame:
    """Apply M & N rules."""
    n = len(parsed_df)
    m_vals = [""] * n
    n_vals = [""] * n

    if not configs:
        return pd.DataFrame({"M": m_vals, "N": n_vals})

    rules = []
    for cfg in configs:
        rules.append({
            "fluid_code":      (cfg.get("fluid_code")      or "").strip(),
            "pipe_class":      (cfg.get("pipe_class")       or "").strip(),
            "nor_op_pressure": (cfg.get("nor_op_pressure")  or "").strip(),
            "nor_op_temp":     (cfg.get("nor_op_temp")      or "").strip(),
        })

    fluid_col = parsed_df["Fluid Code"].astype(str).str.strip() if "Fluid Code" in parsed_df.columns else pd.Series([""] * n)
    class_col = parsed_df["Pipe Class"].astype(str).str.strip()  if "Pipe Class"  in parsed_df.columns else pd.Series([""] * n)

    for i in range(n):
        row_fluid = fluid_col.iloc[i]
        row_class = class_col.iloc[i]
        for rule in rules:
            fluid_ok = (rule["fluid_code"] == "") or (rule["fluid_code"] == row_fluid)
            class_ok = (rule["pipe_class"] == "")  or (rule["pipe_class"] == row_class)
            if fluid_ok and class_ok:
                m_vals[i] = rule["nor_op_pressure"]
                n_vals[i] = rule["nor_op_temp"]
                break

    return pd.DataFrame({"M": m_vals, "N": n_vals})


def write_to_template(template_path: str, df: pd.DataFrame, parsed_df: pd.DataFrame,
                      output_path: str, configs: list = None):
    """Load template, clear existing data rows, and write segregated fields."""
    wb = load_workbook(template_path)
    ws = get_target_sheet(wb)
    press_col, temp_col = get_mn_target_columns(ws)

    # Clear previous data rows safely
    for row in ws.iter_rows(min_row=DATA_START_ROW, max_row=ws.max_row):
        for cell in row:
            if not isinstance(cell, MergedCell):
                cell.value = None

    mn_df = _apply_mn_rules(parsed_df, configs) if configs else None

    for i in range(len(df)):
        excel_row = DATA_START_ROW + i
        fill = ROW_FILL_ODD if i % 2 == 0 else ROW_FILL_EVEN

        # 1. Col A: Sr. No
        sr_no = get_sr_no(df, i)
        _write_cell(ws, excel_row, "A", sr_no, fill)

        # 2. Col B: Drawing No
        drawing_no = get_drawing_no(df, i)
        _write_cell(ws, excel_row, "B", drawing_no, fill)

        # 3. Parsed LINE fields (C=Nominal dia, D=Fluid Code, E=Seq No, I=Pipe Class, T=Tracing, U=Insulation)
        for field, col_letter in PARSED_COL_MAP.items():
            value = parsed_df[field].iloc[i] if field in parsed_df.columns else ""
            _write_cell(ws, excel_row, col_letter, value, fill)

        # 4. Direct mapped columns
        for src_col, tpl_col in COL_MAP.items():
            match = next((c for c in df.columns if c.strip().upper() == src_col.strip().upper()), None)
            value = df[match].iloc[i] if match else ""
            _write_cell(ws, excel_row, tpl_col, value, fill)

        # 5. Nor. Op. Pressure and Nor. Op. Temp
        if mn_df is not None:
            m_val = mn_df["M"].iloc[i]
            n_val = mn_df["N"].iloc[i]
            if m_val != "":
                _write_cell(ws, excel_row, press_col, m_val, fill)
            if n_val != "":
                _write_cell(ws, excel_row, temp_col, n_val, fill)

    wb.save(output_path)
    print(f"Saved -> {output_path}")


def process_file(input_path: str, template_path: str, output_path: str) -> pd.DataFrame:
    """Read input Excel, parse LINE column, export to template. Returns combined df for preview."""
    df = load_input_dataframe(input_path)

    line_col = find_line_column(df)
    if line_col != LINE_SOURCE_COL:
        df = df.rename(columns={line_col: LINE_SOURCE_COL})

    parsed_df = get_parsed_df_from_input(df)

    os.makedirs(os.path.dirname(output_path) if os.path.dirname(output_path) else ".", exist_ok=True)
    write_to_template(template_path, df, parsed_df, output_path, configs=None)

    # Attach Drawing No for preview
    df_copy = df.reset_index(drop=True).copy()
    if "Drawing No" not in df_copy.columns:
        df_copy.insert(0, "Drawing No", [get_drawing_no(df_copy, i) for i in range(len(df_copy))])

    return pd.concat([df_copy, parsed_df.reset_index(drop=True)], axis=1)


def export_with_mn_configs(input_path: str, template_path: str,
                           output_path: str, configs: list) -> str:
    """Re-export applying M & N values."""
    df = load_input_dataframe(input_path)

    line_col = find_line_column(df)
    if line_col != LINE_SOURCE_COL:
        df = df.rename(columns={line_col: LINE_SOURCE_COL})

    parsed_df = get_parsed_df_from_input(df)

    os.makedirs(os.path.dirname(output_path) if os.path.dirname(output_path) else ".", exist_ok=True)
    write_to_template(template_path, df, parsed_df, output_path, configs=configs)
    return output_path


def merge_multiple_files(input_paths: list, template_path: str,
                         output_path: str, configs: list = None) -> tuple:
    """Merge multiple Excel input files into a single output workbook."""
    all_dfs = []
    all_parsed = []

    for input_path in input_paths:
        if not os.path.isfile(input_path):
            continue
        try:
            df = load_input_dataframe(input_path)
            line_col = find_line_column(df)
            if line_col != LINE_SOURCE_COL:
                df = df.rename(columns={line_col: LINE_SOURCE_COL})

            parsed_df = get_parsed_df_from_input(df)

            all_dfs.append(df.reset_index(drop=True))
            all_parsed.append(parsed_df.reset_index(drop=True))
        except Exception as e:
            print(f"Warning: error loading {input_path}: {e}")

    if not all_dfs:
        raise ValueError("No valid input files found with LINE column")

    merged_df = pd.concat(all_dfs, ignore_index=True)
    merged_parsed = pd.concat(all_parsed, ignore_index=True)

    os.makedirs(os.path.dirname(output_path) if os.path.dirname(output_path) else ".", exist_ok=True)
    write_to_template(template_path, merged_df, merged_parsed, output_path, configs=configs)

    merged_df_copy = merged_df.copy()
    if "Drawing No" not in merged_df_copy.columns:
        merged_df_copy.insert(0, "Drawing No", [get_drawing_no(merged_df_copy, i) for i in range(len(merged_df_copy))])

    combined_df = pd.concat([merged_df_copy, merged_parsed], axis=1)
    return output_path, len(merged_df), combined_df


def process_file_with_mn(input_path: str, template_path: str,
                         output_path: str, mn_mapping: dict):
    """Wrapper for backwards compat."""
    configs = []
    for key_str, vals in (mn_mapping or {}).items():
        try:
            key = json.loads(key_str)
        except Exception:
            key = {}
        configs.append({
            "fluid_code":      (key.get("fluid_code")  or "").strip(),
            "pipe_class":      (key.get("pipe_class")   or "").strip(),
            "nor_op_pressure": (vals.get("nor_op_pressure") or "").strip(),
            "nor_op_temp":     (vals.get("nor_op_temp")     or "").strip(),
        })
    return export_with_mn_configs(input_path, template_path, output_path, configs)