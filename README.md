# Avallc-Hybrid-Ai-OS-Ubuntu

## AAVA source discovery workflow

This repo now includes two helper scripts for building a complete understanding of your source materials.


## Quick start (one command)

To begin immediately, run the kickoff orchestrator. It attempts bootstrap + deep scan + PDF scans and writes a timestamped report in `reports/`.

```bash
./tools/start_aava_migration.sh AAVA_Project_vNext /workspace
```

## 0) Bootstrap a working copy of the project

Use this to copy your source project into a new working folder and rename it.

```bash
./tools/bootstrap_aava_project.sh <new-project-name> <destination-root>
```

Example:

```bash
./tools/bootstrap_aava_project.sh AAVA_Project_vNext /workspace
```

Source priority used by the script:

1. `D:\AAVA_Project_clean`
2. `E:\AAVA_Final_Backup`

If those Windows drives are mounted in Linux/WSL (`/mnt/d`, `/mnt/e`), the script automatically finds the first existing source and copies it.

## 1) Deep source scan

Run this first to inspect your Windows source locations and gather inventories of PDFs, likely repos, and key project files.

```bash
./tools/deep_scan_aava_sources.sh
```

Default targets:

- `D:\AAVA_Project_clean`
- `C:\Users\David\Music`
- `C:\Users\David\Downloads`
- `E:\AAVA_Final_Backup`

You can also pass custom paths:

```bash
./tools/deep_scan_aava_sources.sh 'D:\AAVA_Project_clean' 'C:\Users\David\Downloads'
```

## 2) PDF version discovery helper

Use this script to scan PDFs and extract likely iOS/AIOS/AI OS version markers:

```bash
./tools/find_versions_from_pdfs.sh <search-root>
```

Examples:

```bash
./tools/find_versions_from_pdfs.sh /workspace
./tools/find_versions_from_pdfs.sh 'C:\Users\David\Downloads'
```

## What it searches for

The PDF scanner prints lines that match:

- `iOS`
- `AIOS`
- `AI OS`
- `version`
- `release`
- `build`
- `ubuntu`

## Extractor fallback order

The PDF scanner uses the first available method:

1. `pdftotext`
2. `python3` + `pypdf`
3. `strings` (best-effort fallback)

## Path translation note

If you pass a Windows path (for example `C:\Users\David\Downloads`) in Linux/WSL, it is translated to `/mnt/c/Users/David/Downloads` automatically.
