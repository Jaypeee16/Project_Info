# Secure Journal Application

A local desktop journal app built with Python + customtkinter.

## Features

- Dark, minimal desktop UI.
- Playfair encryption for title, tags, mood.
- XOR + hexadecimal encryption for main journal content.
- Local JSON storage with encrypted fields only.
- Atomic save writes plus rolling backup restore.

## Run Locally (Dev)

1. Create and activate a virtual environment.
2. Install runtime dependencies:

```powershell
python -m pip install -r requirements.txt
```

3. Start the app:

```powershell
python secure_journal_app.py
```

## Data Files

- Primary data store: `journal_data.json`
- Backup file: `journal_data.json.bak`

Both files are created in the same folder as the script/executable.

## Package for Windows (.exe)

Use the included build script:

```powershell
.\build_windows.ps1
```

If PowerShell blocks script execution, run:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\build_windows.ps1
```

One-file executable build:

```powershell
.\build_windows.ps1 -OneFile
```

Build output:

- Default: `dist\SecureJournal\`
- One-file: `dist\SecureJournal.exe`

Executable metadata and branding:

- App icon: `assets/secure_journal.ico`
- Version metadata: `version_info.txt`

## Release Checklist

1. Run local app and verify create/edit/save/delete flow works.
2. Confirm encrypted storage in `journal_data.json` and backup behavior with `journal_data.json.bak`.
3. Build package using `./build_windows.ps1` (or `-OneFile` variant).
4. Launch `dist\SecureJournal\SecureJournal.exe` (or one-file exe) and smoke test startup, save, reopen.
5. Verify executable properties show expected version metadata and icon.
6. Ensure `README.md`, `requirements.txt`, and `requirements-packaging.txt` are up to date.
7. Remove local test entries from production release bundle if needed.

## Notes

- Current encryption keys are hardcoded by design for this version.
- Classical Playfair behavior merges `J` with `I`.
