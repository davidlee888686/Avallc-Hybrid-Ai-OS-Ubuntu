# Avallc-Hybrid-Ai-OS-Ubuntu

## AAVA / AIIOS transition workflow (Python)

This repo includes a Python CLI to move from project discovery into an AI-first OS architecture path.

## Quick start

```bash
python3 tools/aava_migration.py kickoff --new-name AAVA_Project_vNext --dest-root /workspace
```

Optional strict mode (returns non-zero if any step fails):

```bash
python3 tools/aava_migration.py kickoff --new-name AAVA_Project_vNext --dest-root /workspace --fail-on-error
```

## Create an AIIOS scaffold (start building now)

```bash
python3 tools/aava_migration.py init-aiios --root aiios_workspace
```

This creates an architecture skeleton:

- `control_plane/`
- `execution_plane/`
- `observability/`
- `ui/`
- `configs/system_profile.example.yaml`

## Existing commands

### Bootstrap copy

```bash
python3 tools/aava_migration.py bootstrap --new-name AAVA_Project_vNext --dest-root /workspace
```

### Deep scan Windows source paths

```bash
python3 tools/aava_migration.py deep-scan
python3 tools/aava_migration.py deep-scan --output json
```

Default paths:

- `D:\AAVA_Project_clean`
- `C:\Users\David\Music`
- `C:\Users\David\Downloads`
- `E:\AAVA_Final_Backup`

### PDF marker scan

```bash
python3 tools/aava_migration.py pdf-scan --search-root 'C:\Users\David\Downloads'
python3 tools/aava_migration.py pdf-scan --search-root 'C:\Users\David\Downloads' --output json
```

Markers:

- `iOS`
- `AIOS`
- `AI OS`
- `version`
- `release`
- `build`
- `ubuntu`

## Architecture blueprint

See `docs/aiios_system_blueprint.md` for the target design:

- AI-first control plane
- Windows host-primary strategy (AIWinOS path)
- Native Linux AIOS strategy (AIIOS/AIISO path)
- Security, milestones, and next implementation steps



## First build preparation (recommended)

```bash
python3 tools/aava_migration.py first-build-prep --project-root . --version 1.0 --skip-tests --note "initial prep"
```

This executes backup + version snapshot + optional chat note + preflight in one step.

## Preflight before build/run/launch

Run one command before major operations:

```bash
python3 tools/aava_migration.py preflight --project-root . --backup-before --backup-source . --backup-root backups
```

This checks dependency status, optionally creates a backup snapshot, optionally runs tests, and writes a report to `reports/preflight_<timestamp>.json`.

## Run tests

```bash
python3 -m unittest discover -s tests -v
```


### Dependency doctor

```bash
python3 tools/aava_migration.py doctor
python3 tools/aava_migration.py doctor --output json
```

Optional install of extra PDF parser (`pypdf`):

```bash
python3 tools/aava_migration.py doctor --install-optional
```

## Dependency policy (toward zero-dependency core)

- **Core runtime goal:** Python standard library only.
- **Optional tools:** `pdftotext`, `strings`, and `pypdf` are treated as optional accelerators/fallbacks.
- **Autonomy model:** orchestration can be increasingly automated, but policy/safety controls remain explicit.


### Backup before every update

Create a timestamped archive backup:

```bash
python3 tools/aava_migration.py backup --source . --backup-root backups --label preupdate
```

### Register and keep one snapshot per version (1.0, 1.5, 2.0)

```bash
python3 tools/aava_migration.py register-version --version 1.0 --source . --vault versions
python3 tools/aava_migration.py register-version --version 1.5 --source . --vault versions
```

This keeps a single snapshot directory per `major.minor` version key and updates `versions/manifest.json`.

### Save chats locally

```bash
python3 tools/aava_migration.py save-chat --text "chat content" --source manual
# or
python3 tools/aava_migration.py save-chat --file ./some_chat_export.txt --source import
```

### Transparency and control model

- This repository contains no hidden censorship module in the CLI tool path; behavior is explicit in source.
- Automation and autonomy should remain policy-controlled and auditable.



### Compare registered versions

```bash
python3 tools/aava_migration.py compare-versions --vault versions --from-version 1.0 --to-version 1.5 --output json
```

### Generate feature checklist manifest (tabs, studio, training, swarm)

```bash
python3 tools/aava_migration.py feature-manifest --version 1.5 --output docs/feature_manifest.json
```

Fill in implementation status in that manifest while deciding the final “best” version.

### Ultimate multi-folder merge (best-of build)

Use this to merge multiple source trees into one combined project with conflict strategy control:

```bash
python3 tools/aava_migration.py ultimate-merge   --sources 'D:\AAVA_Project.worktrees\copilot-worktree-2026-02-18T13-13-40' 'D:\Super_Agent_Ork' 'D:\New folder' 'D:\AAVA_Backups' 'D:\AAVA_Project' 'D:\AAVA_Project_clean' 'E:\AAVA_Final_Backup'   --output-root merge_output   --strategy newest
```

Strategies:

- `first` keep first seen file
- `newest` keep newer mtime (default)
- `largest` keep larger file

Outputs:

- merged files: `merge_output/merged_project/`
- merge report: `merge_output/merge_report/merge_report.json`
