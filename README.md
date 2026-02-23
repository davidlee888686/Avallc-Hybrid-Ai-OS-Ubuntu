# Avallc-Hybrid-Ai-OS-Ubuntu

## AAVA source discovery workflow (Python)

This repository now includes a Python-based CLI for better structure and maintainability than shell-only orchestration.

## Quick start (one command)

```bash
python3 tools/aava_migration.py kickoff --new-name AAVA_Project_vNext --dest-root /workspace
```

This runs bootstrap + deep scan + PDF scans and writes a timestamped report to `reports/<UTC_TIMESTAMP>/`.

## Commands

### 1) Bootstrap a renamed working copy

```bash
python3 tools/aava_migration.py bootstrap --new-name AAVA_Project_vNext --dest-root /workspace
```

Default source priority:

1. `D:\AAVA_Project_clean`
2. `E:\AAVA_Final_Backup`

### 2) Deep scan source locations

```bash
python3 tools/aava_migration.py deep-scan
```

Default scan targets:

- `D:\AAVA_Project_clean`
- `C:\Users\David\Music`
- `C:\Users\David\Downloads`
- `E:\AAVA_Final_Backup`

### 3) Scan PDFs for version markers

```bash
python3 tools/aava_migration.py pdf-scan --search-root 'C:\Users\David\Downloads'
```

Markers searched:

- `iOS`
- `AIOS`
- `AI OS`
- `version`
- `release`
- `build`
- `ubuntu`

Extractor fallback order:

1. `pdftotext`
2. `python3 + pypdf`
3. `strings`

## Path translation note

Windows paths are translated automatically when running in Linux/WSL:

- `C:\Users\...` -> `/mnt/c/Users/...`
- `D:\...` -> `/mnt/d/...`
- `E:\...` -> `/mnt/e/...`
