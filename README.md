# PyAEDT HFSS Exporter

Export HFSS/AEDT design metadata with PyAEDT into readable text files and structured JSON.

The tool attaches to a running Ansys Electronics Desktop session when possible, or opens a selected `.aedt` project. Each run writes a timestamped export folder under the project-local `hfss_exports/` directory by default.

## Requirements

- Windows with Ansys Electronics Desktop / HFSS 2022 R1 or later
- A valid AEDT/HFSS license
- Python 3.10 or newer

## Easy Setup for Windows

For non-technical users:

1. Install Python 3.10 or newer from <https://www.python.org/downloads/windows/>.
   During installation, select **Add python.exe to PATH**.
2. Double-click `setup.bat`.
3. Open your HFSS project in Ansys Electronics Desktop, then double-click `run_exporter.bat`.

`setup.bat` creates a local `.venv` folder and installs PyAEDT and psutil from `requirements.txt`.

## Manual Setup

Install Python dependencies manually:

```powershell
python -m pip install -r requirements.txt
```

## Usage

Easy run after setup:

```powershell
.\run_exporter.bat
```

`run_exporter.bat` forwards arguments to `hfss_exporter.py`, so this also works:

```powershell
.\run_exporter.bat --project "C:\path\to\design.aedt" --design 0
```

Attach to an existing AEDT/HFSS session:

```powershell
python .\hfss_exporter.py
```

Open a specific project:

```powershell
python .\hfss_exporter.py --project "C:\path\to\design.aedt"
```

Select a design by name or zero-based index:

```powershell
python .\hfss_exporter.py --project "C:\path\to\design.aedt" --design 0
```

Override the output base directory:

```powershell
python .\hfss_exporter.py --output-dir "D:\hfss_exports"
```

You can also set `HFSS_EXPORT_BASE_DIR`.

## Output

By default, exports are written inside this repository:

```text
hfss_exports/
+-- hfss_export_YYYYMMDD_HHMMSS/
    +-- 00_manifest_YYYYMMDD_HHMMSS.txt
    +-- 01_variables_classified_YYYYMMDD_HHMMSS.txt
    +-- 02_antenna_smart_summary_YYYYMMDD_HHMMSS.txt
    +-- 03_tree_with_role_YYYYMMDD_HHMMSS.txt
    +-- 04_modeler_full_dump_clean_YYYYMMDD_HHMMSS.txt
    +-- 05_export_data_YYYYMMDD_HHMMSS.json
```

`hfss_exports/` is ignored by Git because exported variables, object names, materials, geometry summaries, and project/design names can contain sensitive design information.

## Notes

This project is not affiliated with, endorsed by, or sponsored by Ansys. It does not include or replace Ansys Electronics Desktop, HFSS, or any required license.

## License

This project is licensed under the MIT License. See [LICENSE](LICENSE).
