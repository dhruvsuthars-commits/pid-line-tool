"""
P&ID Line List Tool — Flask Web App
"""

import os
import json
import pandas as pd
from flask import Flask, request, jsonify, send_file, render_template, session
from dotenv import load_dotenv

# Auto-load environment variables from .env if present
load_dotenv()
load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env"))

from pid_segregate import process_file, export_with_mn_configs, merge_multiple_files
from pid_pdf_ocr import extract_text_and_lines_from_pdf
from line_philosophy_ai import extract_lines_with_philosophy, preview_philosophy_sample

app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "dev-secret-key-change-in-production")

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

SCRIPT_DIR      = os.path.dirname(os.path.abspath(__file__))
TEMPLATES_STORE = os.path.join(SCRIPT_DIR, "templates_store")
OUTPUT_DIR      = os.path.join(SCRIPT_DIR, "output")
INPUT_DIR       = os.path.join(SCRIPT_DIR, "input_store")
TEMPLATE_PATH   = os.path.join(TEMPLATES_STORE, "Linelist_reference.xlsx")

PHILOSOPHIES_STORE = os.path.join(SCRIPT_DIR, "philosophies_store")
if os.environ.get("VERCEL"):
    PHILOSOPHIES_STORE = "/tmp/philosophies_store"
try:
    os.makedirs(PHILOSOPHIES_STORE, exist_ok=True)
except Exception:
    pass

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


from functools import wraps
from flask import redirect, url_for, send_from_directory

DEFAULT_USERNAME = os.environ.get("APP_USER", "dhruvsuthar.ai@gmail.com")
DEFAULT_PASSWORD = os.environ.get("APP_PASSWORD", "Dvs@2585")

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if "user" not in session:
            return redirect(url_for("login", next=request.url))
        return f(*args, **kwargs)
    return decorated_function

# ─────────────────────────────────────────────
# Authentication Routes
# ─────────────────────────────────────────────
@app.route("/login", methods=["GET", "POST"])
def login():
    if "user" in session and request.method == "GET" and not request.args.get("force"):
        return redirect("/")
    error = None
    next_url = request.args.get("next") or request.form.get("next") or "/"
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "").strip()
        if username.lower() == DEFAULT_USERNAME.lower() and password == DEFAULT_PASSWORD:
            session["user"] = username
            return redirect(next_url)
        else:
            error = "Access Denied: Invalid email or password."
    return render_template("login.html", error=error, next_url=next_url)


@app.route("/logout")
def logout():
    session.pop("user", None)
    return redirect(url_for("login"))

# ─────────────────────────────────────────────
# Protected Web Application Routes
# ─────────────────────────────────────────────
@app.route("/")
@login_required
def index():
    # If using GCS and template is not present locally, try to fetch it
    if USE_GCS and GCS_BUCKET and not os.path.exists(TEMPLATE_PATH):
        try:
            gcs_download(GCS_BUCKET, "templates/Linelist_reference.xlsx", TEMPLATE_PATH)
        except Exception:
            pass
    return render_template("index.html", template_loaded=os.path.exists(TEMPLATE_PATH), current_user=session.get("user"))


@app.route("/presentation")
def presentation():
    return render_template("presentation.html", current_user=session.get("user"))


@app.route("/intro-video")
def intro_video():
    return render_template("presentation.html", autoplay_video=True, current_user=session.get("user"))


# ─────────────────────────────────────────────
# Public Access Request & Email Notification
# ─────────────────────────────────────────────
NOTIFICATION_EMAIL = "dhruvsuthar.ai@gmail.com"
ACCESS_REQUESTS_FILE = os.path.join(SCRIPT_DIR, "access_requests.json")

def send_access_notification_email(name, email, company, message):
    smtp_server = os.environ.get("SMTP_SERVER", "smtp.gmail.com")
    smtp_port   = int(os.environ.get("SMTP_PORT", 587))
    smtp_user   = os.environ.get("SMTP_USER", "")
    smtp_pass   = os.environ.get("SMTP_PASSWORD", "")

    email_body = f"""
    📩 NEW P&ID LINE TOOL ACCESS REQUEST

    Name: {name}
    User Email: {email}
    Company / Org: {company}
    Timestamp: {pd.Timestamp.now()}

    Message / Use Case:
    {message}

    ---------------------------------------------------
    Sent automatically to {NOTIFICATION_EMAIL}
    """
    
    if smtp_user and smtp_pass:
        try:
            import smtplib
            from email.mime.text import MIMEText
            from email.mime.multipart import MIMEMultipart
            msg = MIMEMultipart()
            msg['From'] = smtp_user
            msg['To'] = NOTIFICATION_EMAIL
            msg['Subject'] = f"🔔 Access Request: {name} ({company})"
            msg.attach(MIMEText(email_body, 'plain'))

            server = smtplib.SMTP(smtp_server, smtp_port, timeout=5)
            server.starttls()
            server.login(smtp_user, smtp_pass)
            server.send_message(msg)
            server.quit()
            print(f"[SUCCESS] Email notification sent to {NOTIFICATION_EMAIL}")
            return True
        except Exception as e:
            print(f"[WARNING] SMTP send failed: {e}")
            return False
    else:
        print(f"[INFO] Access request logged for {NOTIFICATION_EMAIL}: {name} <{email}> ({company})")
        return True


@app.route("/request-access", methods=["POST"])
def request_access():
    try:
        data = request.get_json(silent=True) or request.form
        name = data.get("name", "").strip()
        email = data.get("email", "").strip()
        company = data.get("company", "").strip()
        user_message = data.get("message", "").strip()

        if not name or not email:
            return jsonify({"error": "Name and email address are required."}), 400

        entry = {
            "id": pd.Timestamp.now().strftime("%Y%m%d%H%M%S"),
            "name": name,
            "email": email,
            "company": company or "N/A",
            "message": user_message or "N/A",
            "timestamp": pd.Timestamp.now().isoformat(),
            "target_notification_email": NOTIFICATION_EMAIL
        }

        requests_list = []
        if os.path.exists(ACCESS_REQUESTS_FILE):
            try:
                with open(ACCESS_REQUESTS_FILE, "r") as f:
                    requests_list = json.load(f)
            except Exception:
                requests_list = []
        requests_list.append(entry)
        with open(ACCESS_REQUESTS_FILE, "w") as f:
            json.dump(requests_list, f, indent=2)

        send_access_notification_email(name, email, company, user_message)

        return jsonify({
            "success": True,
            "message": "Your access request has been sent to the System Administrator! You will receive a response shortly."
        })
    except Exception as e:
        return jsonify({"error": f"Failed to submit request: {str(e)}"}), 500




@app.route("/artifacts/<path:filename>")
@app.route("/_artifacts/<path:filename>")
def serve_artifacts(filename):
    artifact_dir = "/Users/mac/.gemini/antigravity-ide/brain/00df4d73-003d-43ac-8b17-279b522cfa10"
    return send_from_directory(artifact_dir, filename)


@app.route("/download-pptx")
@login_required
def download_pptx():
    root_dir = os.path.dirname(SCRIPT_DIR)
    pptx_path = os.path.join(root_dir, "P_and_ID_Line_Tool_Client_Presentation.pptx")
    if not os.path.exists(pptx_path):
        pptx_path = os.path.join(SCRIPT_DIR, "P_and_ID_Line_Tool_Client_Presentation.pptx")
    return send_file(pptx_path, as_attachment=True, download_name="PID_Line_Tool_Client_Presentation.pptx")







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
# Philosophy Management & Preview Routes
# ─────────────────────────────────────────────
@app.route("/save-philosophy", methods=["POST"])
def save_philosophy():
    data = request.get_json() or {}
    name = (data.get("name") or "").strip()
    text = (data.get("text") or "").strip()

    if not name or not text:
        return jsonify({"error": "Profile name and philosophy text are required."}), 400

    profiles_file = os.path.join(PHILOSOPHIES_STORE, "profiles.json")
    profiles = {}
    if os.path.exists(profiles_file):
        try:
            with open(profiles_file, "r") as f:
                profiles = json.load(f)
        except Exception:
            profiles = {}

    profiles[name] = text

    with open(profiles_file, "w") as f:
        json.dump(profiles, f, indent=2)

    session["active_philosophy"] = text
    session["active_philosophy_name"] = name
    session.modified = True

    return jsonify({"message": f"Philosophy profile '{name}' saved and set as active.", "profiles": profiles})


@app.route("/philosophies", methods=["GET"])
def get_philosophies():
    profiles_file = os.path.join(PHILOSOPHIES_STORE, "profiles.json")
    profiles = {}
    if os.path.exists(profiles_file):
        try:
            with open(profiles_file, "r") as f:
                profiles = json.load(f)
        except Exception:
            profiles = {}
    return jsonify({
        "profiles": profiles,
        "active_name": session.get("active_philosophy_name", ""),
        "active_text": session.get("active_philosophy", "")
    })


@app.route("/set-active-philosophy", methods=["POST"])
def set_active_philosophy():
    data = request.get_json() or {}
    name = data.get("name", "")
    text = data.get("text", "")
    session["active_philosophy_name"] = name
    session["active_philosophy"] = text
    session.modified = True
    return jsonify({"message": "Active philosophy updated.", "active_name": name, "active_text": text})


@app.route("/preview-philosophy", methods=["POST"])
def preview_philosophy():
    data = request.get_json() or {}
    sample_text = (data.get("sample_text") or "").strip()
    philosophy = (data.get("philosophy") or "").strip()

    if not sample_text or not philosophy:
        return jsonify({"error": "Both sample text and philosophy description are required for preview."}), 400

    try:
        results = preview_philosophy_sample(sample_text, philosophy)
        return jsonify({"parsed": results})
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        return jsonify({"error": f"AI Preview failed: {str(e)}"}), 500


# ─────────────────────────────────────────────
# Process PDF with OCR / AI Philosophy Line Extractor
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

    active_philosophy = session.get("active_philosophy", "").strip()

    import fitz
    doc = fitz.open(pdf_path)
    page_texts = [page.get_text("text") for page in doc]
    total_pages = len(doc)
    doc.close()

    lines_found = []
    mode_used = "regex"

    if active_philosophy:
        try:
            lines_found = extract_lines_with_philosophy(page_texts, active_philosophy)
            mode_used = "ai_philosophy"
        except Exception as e:
            # Fallback to regex mode if AI fails or key missing
            print(f"AI Philosophy extraction failed, falling back to regex: {str(e)}")
            ocr_result = extract_text_and_lines_from_pdf(pdf_path)
            lines_found = ocr_result.get("lines", [])
            mode_used = "regex_fallback"
    else:
        ocr_result = extract_text_and_lines_from_pdf(pdf_path)
        lines_found = ocr_result.get("lines", [])

    if not lines_found:
        return jsonify({"error": "No P&ID Line numbers were detected in the uploaded PDF file."}), 400

    ocr_result = {
        "total_pages": total_pages,
        "total_lines_found": len(lines_found),
        "lines": lines_found,
        "mode_used": mode_used
    }

    return jsonify({
        "message": f"Successfully extracted {len(lines_found)} line candidates from PDF across {total_pages} pages ({mode_used} mode).",
        "pdf_info": ocr_result,
        "extracted_lines": lines_found,
        "base_name": base_name,
        "mode_used": mode_used
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

    # 1. Build Excel from confirmed line tags including uploaded PDF file name & dynamic parsed fields
    pdf_file_name = f"{base_name}.pdf"
    excel_rows = []
    
    # Try to locate field dictionaries from session/request if available
    field_map = data.get("field_map", {}) # dict of line_tag -> dict of fields

    for line_obj in selected_lines:
        if isinstance(line_obj, dict):
            line_str = line_obj.get("LINE", "")
            fields = line_obj.get("fields", {})
        else:
            line_str = str(line_obj)
            fields = field_map.get(line_str, {})

        row_dict = {
            "Source PDF Name": pdf_file_name,
            "LINE": line_str
        }
        if fields and isinstance(fields, dict):
            row_dict.update(fields)
        excel_rows.append(row_dict)

    df_pdf_lines = pd.DataFrame(excel_rows)
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
