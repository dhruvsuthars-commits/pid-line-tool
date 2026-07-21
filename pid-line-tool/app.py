"""
P&ID Line List Tool — Flask Web App
"""

import os
import json
import pandas as pd
from flask import Flask, request, jsonify, send_file, render_template, session
from pid_segregate import process_file, export_with_mn_configs, merge_multiple_files
from pid_pdf_ocr import extract_text_and_lines_from_pdf

# Optional Google Cloud Storage integration
USE_GCS = os.environ.get("USE_GCS", "").lower() in ("1", "true", "yes")
GCS_BUCKET = os.environ.get("GCS_BUCKET")
if USE_GCS and GCS_BUCKET:
    try:
        from gcs_utils import upload_file as gcs_upload, download_file as gcs_download, generate_signed_url
    except Exception:
        gcs_upload = gcs_download = generate_signed_url = None
else:
    gcs_upload = gcs_download = generate_signed_url = None


app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "dev-secret-key-change-in-production")

SCRIPT_DIR      = os.path.dirname(os.path.abspath(__file__))
TEMPLATES_STORE = os.path.join(SCRIPT_DIR, "templates_store")
OUTPUT_DIR      = os.path.join(SCRIPT_DIR, "output")
INPUT_DIR       = os.path.join(SCRIPT_DIR, "input_store")
TEMPLATE_PATH   = os.path.join(TEMPLATES_STORE, "Linelist_reference.xlsx")

PORT            = int(os.environ.get("PORT", 5000))
MAX_PORT        = int(os.environ.get("PORT_RANGE_END", 5100))

# On Vercel / serverless, write to /tmp directory if read-only filesystem
if os.environ.get("VERCEL"):
    OUTPUT_DIR      = "/tmp/output"
    TEMPLATES_STORE = "/tmp/templates_store"
    INPUT_DIR       = "/tmp/input_store"
    TEMPLATE_PATH   = os.path.join(TEMPLATES_STORE, "Linelist_reference.xlsx")

try:
    os.makedirs(OUTPUT_DIR,      exist_ok=True)
    os.makedirs(TEMPLATES_STORE, exist_ok=True)
    os.makedirs(INPUT_DIR,       exist_ok=True)
except Exception:
    pass


# ─────────────────────────────────────────────
# Home
# ─────────────────────────────────────────────
@app.route("/")
def index():
    # If using GCS and template is not present locally, try to fetch it
    if USE_GCS and GCS_BUCKET and not os.path.exists(TEMPLATE_PATH):
        try:
            gcs_download(GCS_BUCKET, "templates/Linelist_reference.xlsx", TEMPLATE_PATH)
        except Exception:
            pass
    return render_template("index.html", template_loaded=os.path.exists(TEMPLATE_PATH))


# ─────────────────────────────────────────────
# Upload template
# ─────────────────────────────────────────────
@app.route("/upload-template", methods=["POST"])
def upload_template():
    if "template" not in request.files:
        return jsonify({"error": "No file provided"}), 400

    f = request.files["template"]
    if not f.filename.lower().endswith(".xlsx"):
        return jsonify({"error": "Only .xlsx files are supported"}), 400

    save_path = os.path.join(TEMPLATES_STORE, "Linelist_reference.xlsx")
    f.save(save_path)

    # Optionally upload template to GCS for persistence
    if USE_GCS and GCS_BUCKET and gcs_upload:
        try:
            gcs_upload(GCS_BUCKET, "templates/Linelist_reference.xlsx", save_path)
        except Exception:
            pass

    return jsonify({"message": f"Template '{f.filename}' saved successfully."})


# ─────────────────────────────────────────────
# Process line list
# ─────────────────────────────────────────────
@app.route("/process", methods=["POST"])
def process():
    if "file" not in request.files:
        return jsonify({"error": "No line list file uploaded"}), 400
    # Ensure local template is available (download from GCS if configured)
    if USE_GCS and GCS_BUCKET and not os.path.exists(TEMPLATE_PATH):
        try:
            gcs_download(GCS_BUCKET, "templates/Linelist_reference.xlsx", TEMPLATE_PATH)
        except Exception:
            pass

    if not os.path.exists(TEMPLATE_PATH):
        return jsonify({"error": "No template found. Please upload Linelist_reference first."}), 400

    f = request.files["file"]
    if not f.filename.lower().endswith(".xlsx"):
        return jsonify({"error": "Only .xlsx files are supported"}), 400

    base_name = os.path.splitext(f.filename)[0]
    # Keep input file permanently so /export-with-mn can re-use it
    input_path  = os.path.join(INPUT_DIR,  f"input_{base_name}.xlsx")
    output_path = os.path.join(OUTPUT_DIR, f"{base_name}_Segregated.xlsx")

    f.save(input_path)

    # Optionally upload input to GCS
    if USE_GCS and GCS_BUCKET and gcs_upload:
        try:
            gcs_upload(GCS_BUCKET, f"inputs/{os.path.basename(input_path)}", input_path)
        except Exception:
            pass

    try:
        df_result = process_file(input_path, TEMPLATE_PATH, output_path)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        return jsonify({"error": f"Processing failed: {str(e)}"}), 500

    # Store session state
    session["input_path"]  = input_path
    session["output_name"] = f"{base_name}_Segregated.xlsx"
    session["mn_configs"]  = []   # fresh list for this file
    session.modified = True

    preview_cols   = ["LINE", "Fluid Code", "Sequence No", "Line Size (mm)", "Pipe Class", "Insulation"]
    available_cols = [c for c in preview_cols if c in df_result.columns]
    preview        = df_result[available_cols].head(50).fillna("").to_dict(orient="records")

    fluid_codes  = sorted(df_result["Fluid Code"].dropna().unique().tolist())
    pipe_classes = sorted(df_result["Pipe Class"].dropna().unique().tolist())

    # Optionally upload output to GCS and return signed URL for download
    download_url = None
    if USE_GCS and GCS_BUCKET and gcs_upload and generate_signed_url:
        try:
            remote = f"outputs/{session.get('output_name', os.path.basename(output_path))}"
            gcs_upload(GCS_BUCKET, remote, output_path)
            download_url = generate_signed_url(GCS_BUCKET, remote)
        except Exception:
            download_url = None

    return jsonify({
        "message":     f"Processed {len(df_result)} rows successfully.",
        "rows":        len(df_result),
        "preview":     preview,
        "fluid_codes": fluid_codes,
        "pipe_classes":pipe_classes,
        "download_url": download_url,
    })


# ─────────────────────────────────────────────
# Process PDF with OCR / PyMuPDF Line Extractor
# ─────────────────────────────────────────────
@app.route("/process-pdf", methods=["POST"])
def process_pdf():
    if "pdf_file" not in request.files:
        return jsonify({"error": "No PDF file uploaded"}), 400

    if not os.path.exists(TEMPLATE_PATH):
        return jsonify({"error": "No template found. Please upload Linelist_reference first."}), 400

    f = request.files["pdf_file"]
    if not f.filename.lower().endswith(".pdf"):
        return jsonify({"error": "Only .pdf files are supported for PDF OCR tool"}), 400

    base_name = os.path.splitext(f.filename)[0]
    pdf_path = os.path.join(INPUT_DIR, f"pdf_{base_name}.pdf")
    f.save(pdf_path)

    # 1. Perform PDF OCR / Text line extraction
    ocr_result = extract_text_and_lines_from_pdf(pdf_path)
    lines_found = ocr_result.get("lines", [])

    if not lines_found:
        return jsonify({"error": "No P&ID Line numbers were detected in the uploaded PDF file."}), 400

    # 2. Build temporary Excel file matching input format
    df_pdf_lines = pd.DataFrame([{"LINE": item["LINE"]} for item in lines_found])
    temp_excel_path = os.path.join(INPUT_DIR, f"input_pdf_{base_name}.xlsx")
    df_pdf_lines.to_excel(temp_excel_path, index=False)

    # 3. Segregate into final template Excel
    output_path = os.path.join(OUTPUT_DIR, f"PDF_{base_name}_Segregated.xlsx")
    try:
        df_result = process_file(temp_excel_path, TEMPLATE_PATH, output_path)
    except Exception as e:
        return jsonify({"error": f"Failed to generate line list from extracted PDF data: {str(e)}"}), 500

    # Store session state
    session["input_path"]  = temp_excel_path
    session["output_name"] = f"PDF_{base_name}_Segregated.xlsx"
    session["mn_configs"]  = []
    session.modified = True

    preview_cols   = ["LINE", "Fluid Code", "Sequence No", "Line Size (mm)", "Pipe Class", "Insulation"]
    available_cols = [c for c in preview_cols if c in df_result.columns]
    preview        = df_result[available_cols].fillna("").to_dict(orient="records")

    fluid_codes  = sorted(df_result["Fluid Code"].dropna().unique().tolist())
    pipe_classes = sorted(df_result["Pipe Class"].dropna().unique().tolist())

    return jsonify({
        "message": f"Successfully extracted {len(lines_found)} line candidates from PDF across {ocr_result['total_pages']} pages.",
        "pdf_info": ocr_result,
        "extracted_lines": lines_found,
        "base_name": base_name
    })


# ─────────────────────────────────────────────
# Confirm & Process Selected PDF Lines
# ─────────────────────────────────────────────
@app.route("/confirm-pdf-lines", methods=["POST"])
def confirm_pdf_lines():
    data = request.get_json() or {}
    selected_lines = data.get("selected_lines", [])
    base_name = data.get("base_name", "PDF_Extracted")

    if not selected_lines:
        return jsonify({"error": "No line numbers were selected for inclusion."}), 400

    if not os.path.exists(TEMPLATE_PATH):
        return jsonify({"error": "No template found. Please upload Linelist_reference first."}), 400

    # 1. Build Excel from confirmed line tags including uploaded PDF file name
    pdf_file_name = f"{base_name}.pdf"
    df_pdf_lines = pd.DataFrame([{
        "Source PDF Name": pdf_file_name,
        "LINE": line_str
    } for line_str in selected_lines])
    temp_excel_path = os.path.join(INPUT_DIR, f"input_pdf_{base_name}.xlsx")
    df_pdf_lines.to_excel(temp_excel_path, index=False)

    # 2. Segregate into final template Excel
    output_path = os.path.join(OUTPUT_DIR, f"PDF_{base_name}_Segregated.xlsx")
    try:
        df_result = process_file(temp_excel_path, TEMPLATE_PATH, output_path)
    except Exception as e:
        return jsonify({"error": f"Failed to generate line list from confirmed PDF lines: {str(e)}"}), 500

    # Store session state
    session["input_path"]  = temp_excel_path
    session["output_name"] = f"PDF_{base_name}_Segregated.xlsx"
    session["mn_configs"]  = []
    session.modified = True

    preview_cols   = ["LINE", "Fluid Code", "Sequence No", "Line Size (mm)", "Pipe Class", "Insulation"]
    available_cols = [c for c in preview_cols if c in df_result.columns]
    preview        = df_result[available_cols].fillna("").to_dict(orient="records")

    fluid_codes  = sorted(df_result["Fluid Code"].dropna().unique().tolist())
    pipe_classes = sorted(df_result["Pipe Class"].dropna().unique().tolist())

    return jsonify({
        "message": f"Successfully processed {len(df_result)} selected line numbers into final line list.",
        "rows": len(df_result),
        "preview": preview,
        "fluid_codes": fluid_codes,
        "pipe_classes": pipe_classes,
        "output_name": session["output_name"]
    })





# ─────────────────────────────────────────────
# Process multiple line lists (merge into one)
# ─────────────────────────────────────────────
@app.route("/process-multiple", methods=["POST"])
def process_multiple():
    if "files" not in request.files:
        return jsonify({"error": "No files uploaded"}), 400
    if USE_GCS and GCS_BUCKET and not os.path.exists(TEMPLATE_PATH):
        try:
            gcs_download(GCS_BUCKET, "templates/Linelist_reference.xlsx", TEMPLATE_PATH)
        except Exception:
            pass

    if not os.path.exists(TEMPLATE_PATH):
        return jsonify({"error": "No template found. Please upload Linelist_reference first."}), 400

    files = request.files.getlist("files")
    if not files or len(files) == 0:
        return jsonify({"error": "No files selected"}), 400

    # Save all uploaded files temporarily
    input_paths = []
    for f in files:
        if not f.filename.lower().endswith(".xlsx"):
            return jsonify({"error": f"File '{f.filename}' is not .xlsx"}), 400
        
        base_name = os.path.splitext(f.filename)[0]
        input_path = os.path.join(INPUT_DIR, f"input_{base_name}_{len(input_paths)}.xlsx")
        f.save(input_path)
        input_paths.append(input_path)

    try:
        output_name = f"Merged_Output_{len(files)}files.xlsx"
        output_path = os.path.join(OUTPUT_DIR, output_name)
        
        _, total_rows, df_result = merge_multiple_files(input_paths, TEMPLATE_PATH, output_path, configs=None)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        return jsonify({"error": f"Processing failed: {str(e)}"}), 500

    # Store session state for this merged file
    session["input_paths"]  = input_paths
    session["output_name"]  = output_name
    session["mn_configs"]   = []
    session.modified = True

    preview_cols   = ["LINE", "Fluid Code", "Sequence No", "Line Size (mm)", "Pipe Class", "Insulation"]
    available_cols = [c for c in preview_cols if c in df_result.columns]
    preview        = df_result[available_cols].head(50).fillna("").to_dict(orient="records")

    fluid_codes  = sorted(df_result["Fluid Code"].dropna().unique().tolist())
    pipe_classes = sorted(df_result["Pipe Class"].dropna().unique().tolist())

    # Optionally upload merged output to GCS and return signed URL
    download_url = None
    if USE_GCS and GCS_BUCKET and gcs_upload and generate_signed_url:
        try:
            remote = f"outputs/{os.path.basename(output_path)}"
            gcs_upload(GCS_BUCKET, remote, output_path)
            download_url = generate_signed_url(GCS_BUCKET, remote)
        except Exception:
            download_url = None

    return jsonify({
        "message":     f"Merged {len(files)} files with {total_rows} total rows successfully.",
        "rows":        total_rows,
        "files_count": len(files),
        "preview":     preview,
        "fluid_codes": fluid_codes,
        "pipe_classes": pipe_classes,
        "download_url": download_url,
    })


# ─────────────────────────────────────────────
# Save M & N config
# ─────────────────────────────────────────────
@app.route("/save-mn-config", methods=["POST"])
def save_mn_config():
    data = request.get_json()
    if not data:
        return jsonify({"error": "No data provided"}), 400

    fluid_code      = (data.get("fluid_code")      or "").strip()
    pipe_class      = (data.get("pipe_class")       or "").strip()
    nor_op_pressure = (data.get("nor_op_pressure")  or "").strip()
    nor_op_temp     = (data.get("nor_op_temp")      or "").strip()

    if not nor_op_pressure and not nor_op_temp:
        return jsonify({"error": "Please provide at least M or N value"}), 400

    if "mn_configs" not in session:
        session["mn_configs"] = []

    configs = list(session["mn_configs"])  # copy so Flask detects mutation

    # Replace existing rule for same fluid+class combo, or append new one
    for existing in configs:
        if existing["fluid_code"] == fluid_code and existing["pipe_class"] == pipe_class:
            existing["nor_op_pressure"] = nor_op_pressure
            existing["nor_op_temp"]     = nor_op_temp
            break
    else:
        configs.append({
            "fluid_code":      fluid_code,
            "pipe_class":      pipe_class,
            "nor_op_pressure": nor_op_pressure,
            "nor_op_temp":     nor_op_temp,
        })

    session["mn_configs"] = configs
    session.modified = True

    return jsonify({"message": "M & N configuration saved"})


# ─────────────────────────────────────────────
# Get M & N configs
# ─────────────────────────────────────────────
@app.route("/get-mn-config")
def get_mn_config():
    return jsonify({"configs": session.get("mn_configs", [])})


# ─────────────────────────────────────────────
# Clear M & N configs
# ─────────────────────────────────────────────
@app.route("/clear-mn-config", methods=["POST"])
def clear_mn_config():
    session["mn_configs"] = []
    session.modified = True
    return jsonify({"message": "M & N configuration cleared"})


# ─────────────────────────────────────────────
# Export Excel with M & N applied  ← MAIN FIX
# ─────────────────────────────────────────────
@app.route("/export-with-mn", methods=["POST"])
def export_with_mn():
    """
    Re-run the export with M&N values applied to matching rows.
    Supports both single file (input_path) and multiple files (input_paths).
    """
    body    = request.get_json(silent=True) or {}
    configs = body.get("configs")
    if not configs:
        configs = session.get("mn_configs", [])

    # Check for merged file scenario (multiple input paths)
    input_paths = session.get("input_paths")
    input_path = session.get("input_path")
    
    if input_paths and len(input_paths) > 0:
        # Multiple files - use merge
        if not all(os.path.exists(p) for p in input_paths):
            return jsonify({"error": "Original input files not found. Please re-upload your line lists."}), 400
        
        if not os.path.exists(TEMPLATE_PATH):
            return jsonify({"error": "Template not found. Please upload Linelist_reference template."}), 400

        output_name = session.get("output_name", "Merged_Output.xlsx")
        output_path = os.path.join(OUTPUT_DIR, output_name)

        try:
            merge_multiple_files(input_paths, TEMPLATE_PATH, output_path, configs=configs)
            # persist to GCS as well
            if USE_GCS and GCS_BUCKET and gcs_upload:
                try:
                    gcs_upload(GCS_BUCKET, f"outputs/{os.path.basename(output_path)}", output_path)
                except Exception:
                    pass
        except Exception as e:
            return jsonify({"error": f"Export failed: {str(e)}"}), 500
    else:
        # Single file
        if not input_path or not os.path.exists(input_path):
            return jsonify({"error": "Original input file not found. Please re-upload your line list."}), 400

        if not os.path.exists(TEMPLATE_PATH):
            return jsonify({"error": "Template not found. Please upload Linelist_reference template."}), 400

        output_name = session.get("output_name", "LineList_Segregated.xlsx")
        output_path = os.path.join(OUTPUT_DIR, output_name)

        try:
            export_with_mn_configs(input_path, TEMPLATE_PATH, output_path, configs)
            if USE_GCS and GCS_BUCKET and gcs_upload:
                try:
                    gcs_upload(GCS_BUCKET, f"outputs/{os.path.basename(output_path)}", output_path)
                except Exception:
                    pass
        except Exception as e:
            return jsonify({"error": f"Export failed: {str(e)}"}), 500

    return send_file(
        output_path,
        as_attachment=True,
        download_name=output_name,
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )



# ─────────────────────────────────────────────
# Simple download (no M&N)
# ─────────────────────────────────────────────
@app.route("/download/<filename>")
def download(filename):
    path = os.path.join(OUTPUT_DIR, filename)
    if not os.path.exists(path):
        return jsonify({"error": "File not found"}), 404
    return send_file(path, as_attachment=True, download_name=filename)


# ─────────────────────────────────────────────
# Template status
# ─────────────────────────────────────────────
@app.route("/template-status")
def template_status():
    return jsonify({"loaded": os.path.exists(TEMPLATE_PATH)})


if __name__ == "__main__":
    def find_free_port(start_port, max_port):
        import socket
        host = "0.0.0.0"
        for candidate in range(start_port, max_port + 1):
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
                sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                try:
                    sock.bind((host, candidate))
                    return candidate
                except OSError:
                    continue
        raise OSError(f"No free port found between {start_port} and {max_port}")

    try:
        port = find_free_port(PORT, MAX_PORT)
    except OSError as e:
        print(str(e))
        raise

    if port != PORT:
        print(f"Port {PORT} is in use. Starting server on available port {port} instead.")

    app.run(debug=False, host="0.0.0.0", port=port)
