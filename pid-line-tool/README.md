# PID Line Tool

## Install

Use the project virtual environment in `venv`.

```powershell
cd c:\projects\pid-line-tool\pid-line-tool
.\venv\Scripts\python.exe -m pip install -r requirements.txt
```

## Run the Flask app

```powershell
cd c:\projects\pid-line-tool\pid-line-tool
.\venv\Scripts\python.exe .\app.py
```

Then open:

```text
http://127.0.0.1:5000
```

## Use the CLI directly

```powershell
cd c:\projects\pid-line-tool\pid-line-tool
.\venv\Scripts\python.exe .\pid_segregate.py input\yourfile.xlsx
```

Optional template/output arguments:

```powershell
.\venv\Scripts\python.exe .\pid_segregate.py input\yourfile.xlsx --template templates_store\Linelist_reference.xlsx
.\venv\Scripts\python.exe .\pid_segregate.py input\yourfile.xlsx --output output\myfile_Segregated.xlsx
```
