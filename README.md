# PyAEDT HFSS Exporter

Export HFSS/AEDT design metadata with PyAEDT into readable text files and structured JSON.

The tool attaches to a running Ansys Electronics Desktop session by default. You can also open a `.aedt` project explicitly with `--project`. Each run writes a timestamped export folder under the project-local `hfss_exports/` directory by default.

## Requirements

- Windows with Ansys Electronics Desktop / HFSS 2022 R1 or later
- A valid AEDT/HFSS license
- Python 3.10 through 3.13. Python 3.14 is not currently supported because `pythonnet` does not support it.

## Easy Setup for Windows

For non-technical users:

1. Double-click `setup.bat`.
   If Python 3.10 through 3.13 is not found, setup can install Python 3.13 automatically with `winget`.
2. If setup asks to install Python, approve the prompt and let it finish.
3. Open your HFSS project in Ansys Electronics Desktop, then double-click `run_exporter.bat`.

`setup.bat` creates a local `.venv` folder and installs the Python dependencies from `requirements.txt`. Python 3.10 is preferred when available, but Python 3.11, 3.12, and 3.13 are also accepted. If `winget` is not available, install a supported Python version manually from <https://www.python.org/downloads/windows/>.

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

If no usable AEDT/HFSS session is found, the script stops instead of opening a file picker.

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

## Author

James Huang - [@jameshuang0430](https://github.com/jameshuang0430)
