#!/usr/bin/env python3
"""AAVA migration toolkit (Python version)."""

from __future__ import annotations

import argparse
import datetime as dt
import importlib.util
import json
import os
import tarfile
import hashlib
import re
import shutil
import subprocess
import sys
from itertools import islice
from pathlib import Path
from typing import Any, Iterable, Iterator, List, Optional

DEFAULT_SOURCE_CANDIDATES = [
    r"D:\AAVA_Project_clean",
    r"E:\AAVA_Final_Backup",
]

DEFAULT_SCAN_TARGETS = [
    r"D:\AAVA_Project_clean",
    r"C:\Users\David\Music",
    r"C:\Users\David\Downloads",
    r"E:\AAVA_Final_Backup",
]

KEY_FILE_RE = re.compile(
    r"(^|/)(readme(\.md|\.txt)?|package\.json|pyproject\.toml|requirements\.txt|"
    r"cargo\.toml|go\.mod|pom\.xml|build\.gradle|dockerfile|compose\.ya?ml)$",
    re.IGNORECASE,
)
MARKER_RE = re.compile(r"(^|[^a-z])(ios|aios|ai\s*os|version|release|build|ubuntu)($|[^a-z])", re.IGNORECASE)
SAFE_NAME_RE = re.compile(r"^[A-Za-z0-9._-]+$")

SEMVER2_RE = re.compile(r"^(0|[1-9]\d*)\.(0|[1-9]\d*)$")
DEFAULT_CHAT_LOG = Path("chats") / "chat_history.jsonl"
DEFAULT_BACKUP_ROOT = Path("backups")
DEFAULT_VERSION_VAULT = Path("versions")


def normalize_windows_path(path: str) -> Path:
    p = path.replace("\\", "/")
    m = re.match(r"^([A-Za-z]):/(.*)$", p)
    if m:
        drive = m.group(1).lower()
        rest = m.group(2)
        return Path(f"/mnt/{drive}/{rest}")
    return Path(p)


def iter_pdfs(root: Path) -> Iterator[Path]:
    for dirpath, _, filenames in os.walk(root):
        for name in filenames:
            if name.lower().endswith(".pdf"):
                yield Path(dirpath) / name


def iter_repo_roots(root: Path) -> Iterator[Path]:
    for dirpath, dirnames, _ in os.walk(root):
        if ".git" in dirnames:
            yield Path(dirpath)


def iter_key_files(root: Path) -> Iterator[Path]:
    for dirpath, _, filenames in os.walk(root):
        for name in filenames:
            rel = (Path(dirpath) / name).relative_to(root).as_posix()
            if KEY_FILE_RE.search(rel):
                yield root / rel


def choose_extractor() -> str:
    if shutil.which("pdftotext"):
        return "pdftotext"

    check = subprocess.run(
        [sys.executable, "-c", "import importlib.util,sys;sys.exit(0 if importlib.util.find_spec('pypdf') else 1)"],
        capture_output=True,
        text=True,
    )
    if check.returncode == 0:
        return "python-pypdf"

    if shutil.which("strings"):
        return "strings"

    return "none"




def python_module_available(name: str) -> bool:
    return importlib.util.find_spec(name) is not None


def collect_dependency_status() -> dict[str, Any]:
    tools = {
        "python3": shutil.which("python3") is not None,
        "pdftotext": shutil.which("pdftotext") is not None,
        "strings": shutil.which("strings") is not None,
    }
    py_modules = {"pypdf": python_module_available("pypdf")}
    return {"tools": tools, "python_modules": py_modules}




def ensure_parent(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)


def is_semver2(version: str) -> bool:
    return bool(SEMVER2_RE.fullmatch(version))


def create_tar_backup(source: Path, backup_root: Path, label: str) -> Path:
    backup_root.mkdir(parents=True, exist_ok=True)
    ts = dt.datetime.now(dt.UTC).strftime("%Y%m%dT%H%M%SZ")
    safe_label = re.sub(r"[^A-Za-z0-9._-]", "_", label)
    out = backup_root / f"{safe_label}_{ts}.tar.gz"
    with tarfile.open(out, "w:gz") as tf:
        tf.add(source, arcname=source.name)
    return out


def cmd_backup(args: argparse.Namespace) -> int:
    source = normalize_windows_path(args.source)
    if not source.exists():
        print(f"ERROR: Source path does not exist: {source}", file=sys.stderr)
        return 2

    backup_root = Path(args.backup_root)
    archive = create_tar_backup(source, backup_root, args.label or source.name)
    print(f"Backup created: {archive}")
    return 0


def cmd_register_version(args: argparse.Namespace) -> int:
    if not is_semver2(args.version):
        print("ERROR: Version must be major.minor format like 1.0 or 1.5", file=sys.stderr)
        return 2

    source = normalize_windows_path(args.source)
    if not source.exists() or not source.is_dir():
        print(f"ERROR: Source directory does not exist: {source}", file=sys.stderr)
        return 2

    vault = Path(args.vault)
    vault.mkdir(parents=True, exist_ok=True)
    target = vault / args.version

    if target.exists():
        shutil.rmtree(target)

    ignore = shutil.ignore_patterns("versions", "backups", "reports", "chats", "__pycache__")
    shutil.copytree(source, target, ignore=ignore)

    manifest = vault / "manifest.json"
    data: dict[str, Any]
    if manifest.exists():
        data = json.loads(manifest.read_text())
    else:
        data = {"versions": {}}

    data.setdefault("versions", {})[args.version] = {
        "path": str(target),
        "saved_utc": f"{dt.datetime.now(dt.UTC):%Y-%m-%d %H:%M:%S}",
    }
    manifest.write_text(json.dumps(data, indent=2))

    print(f"Version snapshot saved: {target}")
    return 0


def cmd_save_chat(args: argparse.Namespace) -> int:
    log_path = Path(args.log)
    ensure_parent(log_path)

    if args.text:
        content = args.text
    elif args.file:
        f = Path(args.file)
        if not f.is_file():
            print(f"ERROR: Chat file not found: {f}", file=sys.stderr)
            return 2
        content = f.read_text()
    else:
        print("ERROR: provide --text or --file", file=sys.stderr)
        return 2

    entry = {
        "timestamp_utc": f"{dt.datetime.now(dt.UTC):%Y-%m-%d %H:%M:%S}",
        "source": args.source,
        "content": content,
    }
    with log_path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(entry, ensure_ascii=False) + "\n")

    print(f"Chat saved to: {log_path}")
    return 0


def file_sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def cmd_ultimate_merge(args: argparse.Namespace) -> int:
    raw_sources = args.sources
    sources: list[Path] = []
    missing: list[str] = []

    for raw in raw_sources:
        mapped = normalize_windows_path(raw)
        if mapped.is_dir():
            sources.append(mapped)
        else:
            missing.append(f"{raw} -> {mapped}")

    if not sources:
        print("ERROR: none of the provided source folders are available in this environment", file=sys.stderr)
        for m in missing:
            print(f"  - {m}", file=sys.stderr)
        return 2

    out_root = Path(args.output_root)
    merged_root = out_root / "merged_project"
    report_root = out_root / "merge_report"
    merged_root.mkdir(parents=True, exist_ok=True)
    report_root.mkdir(parents=True, exist_ok=True)

    index: dict[str, dict[str, Any]] = {}
    collisions: list[dict[str, Any]] = []
    copied = 0

    for src in sources:
        for dirpath, _, filenames in os.walk(src):
            base = Path(dirpath)
            for name in filenames:
                src_file = base / name
                rel = src_file.relative_to(src).as_posix()
                size = src_file.stat().st_size
                mtime = src_file.stat().st_mtime
                digest = file_sha256(src_file)

                if rel not in index:
                    index[rel] = {
                        "source": str(src_file),
                        "digest": digest,
                        "size": size,
                        "mtime": mtime,
                    }
                    continue

                cur = index[rel]
                if cur["digest"] == digest:
                    continue

                winner = cur
                candidate = {
                    "source": str(src_file),
                    "digest": digest,
                    "size": size,
                    "mtime": mtime,
                }

                if args.strategy == "newest" and candidate["mtime"] > winner["mtime"]:
                    index[rel] = candidate
                    winner = candidate
                elif args.strategy == "largest" and candidate["size"] > winner["size"]:
                    index[rel] = candidate
                    winner = candidate

                collisions.append({
                    "path": rel,
                    "kept": index[rel]["source"],
                    "other": str(src_file),
                })

    for rel, meta in index.items():
        src_file = Path(meta["source"])
        dest = merged_root / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src_file, dest)
        copied += 1

    report = {
        "sources": [str(s) for s in sources],
        "missing_sources": missing,
        "strategy": args.strategy,
        "files_copied": copied,
        "collisions": collisions,
    }
    (report_root / "merge_report.json").write_text(json.dumps(report, indent=2))

    print(f"Merged {copied} files into: {merged_root}")
    print(f"Report: {report_root / 'merge_report.json'}")
    return 0


def cmd_preflight(args: argparse.Namespace) -> int:
    project_root = Path(args.project_root)
    if not project_root.exists() or not project_root.is_dir():
        print(f"ERROR: project root not found: {project_root}", file=sys.stderr)
        return 2

    ts = dt.datetime.now(dt.UTC).strftime("%Y%m%dT%H%M%SZ")
    report_dir = Path(args.report_dir)
    report_dir.mkdir(parents=True, exist_ok=True)

    report: dict[str, Any] = {
        "timestamp_utc": f"{dt.datetime.now(dt.UTC):%Y-%m-%d %H:%M:%S}",
        "project_root": str(project_root),
        "doctor": collect_dependency_status(),
        "backup": None,
        "tests": None,
    }

    if args.backup_before:
        backup_source = normalize_windows_path(args.backup_source)
        if backup_source.exists():
            archive = create_tar_backup(backup_source, Path(args.backup_root), args.backup_label or backup_source.name)
            report["backup"] = {"ok": True, "archive": str(archive)}
        else:
            report["backup"] = {"ok": False, "error": f"source missing: {backup_source}"}

    if not args.skip_tests:
        proc = subprocess.run(
            [sys.executable, "-m", "unittest", "discover", "-s", "tests", "-v"],
            cwd=project_root,
            capture_output=True,
            text=True,
        )
        report["tests"] = {
            "ok": proc.returncode == 0,
            "returncode": proc.returncode,
            "stdout_tail": proc.stdout[-4000:],
            "stderr_tail": proc.stderr[-4000:],
        }

    report_file = report_dir / f"preflight_{ts}.json"
    report_file.write_text(json.dumps(report, indent=2))

    print(f"Preflight report: {report_file}")
    if args.output == "json":
        print(json.dumps(report, indent=2))

    tests_ok = report["tests"] is None or report["tests"]["ok"]
    backup_ok = report["backup"] is None or report["backup"]["ok"]
    return 0 if (tests_ok and backup_ok) else 1

def cmd_doctor(args: argparse.Namespace) -> int:
    status = collect_dependency_status()

    if args.install_optional and not status["python_modules"]["pypdf"]:
        proc = subprocess.run([sys.executable, "-m", "pip", "install", "pypdf"], capture_output=True, text=True)
        status["install_attempt"] = {
            "package": "pypdf",
            "returncode": proc.returncode,
            "stdout": proc.stdout[-2000:],
            "stderr": proc.stderr[-2000:],
        }
        status = collect_dependency_status() | {"install_attempt": status.get("install_attempt")}

    if args.output == "json":
        print(json.dumps(status, indent=2))
        return 0

    print("== Dependency Doctor ==")
    for k, v in status["tools"].items():
        print(f"- tool:{k}: {'OK' if v else 'MISSING'}")
    for k, v in status["python_modules"].items():
        print(f"- module:{k}: {'OK' if v else 'MISSING'}")

    if "install_attempt" in status:
        attempt = status["install_attempt"]
        print(f"- install_attempt:{attempt['package']}: returncode={attempt['returncode']}")

    return 0

def extract_pdf_text(pdf_path: Path, extractor: str) -> Optional[str]:
    if extractor == "pdftotext":
        proc = subprocess.run(["pdftotext", "-layout", str(pdf_path), "-"], capture_output=True, text=True)
        return proc.stdout if proc.returncode == 0 else None

    if extractor == "python-pypdf":
        code = (
            "from pypdf import PdfReader\n"
            "import sys\n"
            "r=PdfReader(sys.argv[1])\n"
            "print('\\n\\n'.join((p.extract_text() or '') for p in r.pages))\n"
        )
        proc = subprocess.run([sys.executable, "-c", code, str(pdf_path)], capture_output=True, text=True)
        return proc.stdout if proc.returncode == 0 else None

    if extractor == "strings":
        proc = subprocess.run(["strings", str(pdf_path)], capture_output=True, text=True)
        return proc.stdout if proc.returncode == 0 else None

    return None


def is_safe_project_name(name: str) -> bool:
    return bool(SAFE_NAME_RE.fullmatch(name))


def cmd_bootstrap(args: argparse.Namespace) -> int:
    if not is_safe_project_name(args.new_name):
        print("ERROR: --new-name contains unsupported characters. Use letters, digits, . _ -", file=sys.stderr)
        return 2

    dest_root = Path(args.dest_root)
    if not dest_root.is_dir():
        print(f"ERROR: Destination root does not exist: {dest_root}", file=sys.stderr)
        return 2

    source_candidates = args.sources or DEFAULT_SOURCE_CANDIDATES
    selected: Optional[Path] = None
    for candidate in source_candidates:
        mapped = normalize_windows_path(candidate)
        if mapped.is_dir():
            selected = mapped
            break

    if selected is None:
        print("ERROR: Could not find source folder in this environment.", file=sys.stderr)
        print("Checked:", file=sys.stderr)
        for c in source_candidates:
            print(f"  - {c} (mapped: {normalize_windows_path(c)})", file=sys.stderr)
        return 2

    target = dest_root / args.new_name
    if target.exists():
        print(f"ERROR: Target already exists: {target}", file=sys.stderr)
        return 2

    print(f"Selected source: {selected}")
    print(f"Creating working copy: {target}")
    shutil.copytree(selected, target)
    print("Copy complete.")
    return 0


def cmd_deep_scan(args: argparse.Namespace) -> int:
    targets = args.paths or DEFAULT_SCAN_TARGETS
    results: List[dict[str, Any]] = []

    for raw in targets:
        mapped = normalize_windows_path(raw)
        item: dict[str, Any] = {"input": raw, "mapped": str(mapped), "status": "missing"}

        if not mapped.exists():
            results.append(item)
            continue

        if mapped.is_file():
            item["status"] = "file"
            results.append(item)
            continue

        item["status"] = "directory"
        item["top_entries"] = [str(p) for p in islice(mapped.iterdir(), 50)]
        item["pdf_files"] = [str(p) for p in islice(iter_pdfs(mapped), 200)]
        item["repo_roots"] = [str(r) for r in islice(iter_repo_roots(mapped), 100)]
        item["key_files"] = [str(f) for f in islice(iter_key_files(mapped), 200)]
        results.append(item)

    if args.output == "json":
        print(json.dumps({"timestamp_utc": f"{dt.datetime.now(dt.UTC):%Y-%m-%d %H:%M:%S}", "targets": results}, indent=2))
        return 0

    print("== AAVA deep scan ==")
    print(f"UTC timestamp: {dt.datetime.now(dt.UTC):%Y-%m-%d %H:%M:%S}")
    print()

    found_any = False
    for item in results:
        print("## Target")
        print(f"- Input:  {item['input']}")
        print(f"- Mapped: {item['mapped']}")
        status = item["status"]

        if status == "missing":
            print("- Status: MISSING in this environment")
            print()
            continue

        found_any = True
        if status == "file":
            print("- Status: FILE")
            print()
            continue

        print("- Status: DIRECTORY")
        print("- Top-level entries:")
        for p in item["top_entries"]:
            print(f"  - {p}")

        print("- PDF files (first 200):")
        for p in item["pdf_files"]:
            print(f"  - {p}")

        print("- Likely repo roots (first 100):")
        for r in item["repo_roots"]:
            print(f"  - {r}")

        print("- Key project files (first 200):")
        for f in item["key_files"]:
            print(f"  - {f}")
        print()

    if not found_any:
        print("No target paths are mounted/available in this environment.")
        print("If using WSL/Linux, mount C:/D:/E: under /mnt/c, /mnt/d, /mnt/e.")
    return 0


def cmd_pdf_scan(args: argparse.Namespace) -> int:
    root = normalize_windows_path(args.search_root)
    if not root.is_dir():
        print(f"ERROR: Search root does not exist in this environment: {root}", file=sys.stderr)
        return 2

    pdfs = list(iter_pdfs(root))
    if not pdfs:
        print(f"No PDFs found under: {root}")
        return 0

    extractor = choose_extractor()
    if extractor == "none":
        print("ERROR: No extractor available (install pdftotext, pypdf, or strings).", file=sys.stderr)
        return 2

    if args.output == "json":
        payload: dict[str, Any] = {"root": str(root), "extractor": extractor, "pdf_count": len(pdfs), "results": []}
    else:
        print(f"Found {len(pdfs)} PDF(s). Using extractor: {extractor}")
        print("Scanning for markers: iOS, AIOS, AI OS, version, release, build, ubuntu")

    for pdf in pdfs:
        text = extract_pdf_text(pdf, extractor)
        if text is None:
            if args.output == "json":
                payload["results"].append({"pdf": str(pdf), "error": f"Unable to parse with extractor: {extractor}"})
            else:
                print(f"\n=== {pdf} ===")
                print(f"(Unable to parse with extractor: {extractor})")
            continue

        matches: list[str] = []
        for i, line in enumerate(text.splitlines(), start=1):
            if MARKER_RE.search(line):
                matches.append(f"{i}:{line}")
                if len(matches) >= 80:
                    break

        if args.output == "json":
            payload["results"].append({"pdf": str(pdf), "matches": matches})
        else:
            print(f"\n=== {pdf} ===")
            if matches:
                for m in matches:
                    print(m)
            else:
                print("(No matching markers found)")

    if args.output == "json":
        print(json.dumps(payload, indent=2))

    return 0


def cmd_kickoff(args: argparse.Namespace) -> int:
    ts = dt.datetime.now(dt.UTC).strftime("%Y%m%dT%H%M%SZ")
    report_dir = Path("reports") / ts
    report_dir.mkdir(parents=True, exist_ok=True)
    report_file = report_dir / "kickoff_report.md"

    steps = [
        ("Bootstrap copy", ["bootstrap", "--new-name", args.new_name, "--dest-root", args.dest_root]),
        ("Deep scan default targets", ["deep-scan"]),
        ("PDF scan Downloads", ["pdf-scan", "--search-root", r"C:\Users\David\Downloads"]),
        ("PDF scan Music", ["pdf-scan", "--search-root", r"C:\Users\David\Music"]),
    ]

    report_lines: List[str] = [
        "# AAVA Migration Kickoff Report",
        "",
        f"- UTC time: {dt.datetime.now(dt.UTC):%Y-%m-%d %H:%M:%S}",
        f"- Requested working copy name: {args.new_name}",
        f"- Destination root: {args.dest_root}",
        "",
    ]

    failed_steps = 0
    for title, step_args in steps:
        cmd = [sys.executable, __file__, *step_args]
        proc = subprocess.run(cmd, capture_output=True, text=True)
        log_name = f"{title.replace(' ', '_')}.log"
        combined = proc.stdout + ("\n" + proc.stderr if proc.stderr else "")
        (report_dir / log_name).write_text(combined)

        if proc.returncode != 0:
            failed_steps += 1

        report_lines.extend(
            [
                f"## {title}",
                "",
                f"- Command: `{' '.join(step_args)}`",
                f"- Exit code: {proc.returncode}",
                f"- Log file: `{log_name}`",
                "",
            ]
        )

    report_lines.extend(["## Summary", "", f"- Failed steps: {failed_steps} of {len(steps)}", ""])
    report_file.write_text("\n".join(report_lines))
    print("Kickoff complete.")
    print(f"Report: {report_file}")
    print(f"Logs:   {report_dir}/*.log")

    if args.fail_on_error and failed_steps > 0:
        return 1
    return 0


def cmd_init_aiios(args: argparse.Namespace) -> int:
    root = Path(args.root)
    root.mkdir(parents=True, exist_ok=True)

    dirs = [
        root / "control_plane" / "policy",
        root / "control_plane" / "planner",
        root / "execution_plane" / "adapters" / "linux",
        root / "execution_plane" / "adapters" / "windows",
        root / "execution_plane" / "runtimes" / "containers",
        root / "execution_plane" / "runtimes" / "vm",
        root / "execution_plane" / "runtimes" / "subsystem",
        root / "observability" / "telemetry",
        root / "observability" / "audit",
        root / "ui" / "dashboard",
        root / "ui" / "console",
        root / "configs",
        root / "scripts",
        root / "docs",
    ]

    for d in dirs:
        d.mkdir(parents=True, exist_ok=True)

    module_readme = root / "README.md"
    if not module_readme.exists():
        module_readme.write_text(
            """# AIIOS Workspace

Generated scaffold for AI-first OS control platform.

## Layers
- control_plane
- execution_plane
- observability
- ui
"""
        )

    profile = root / "configs" / "system_profile.example.yaml"
    if not profile.exists():
        profile.write_text(
            """name: AIIOS-Host
mode: host-primary
host: windows
safety:
  require_approval_for:
    - registry_changes
    - boot_config_changes
    - firewall_changes
execution:
  preferred_runtime: container
  allow_vm_fallback: true
"""
        )

    print(f"Initialized AIIOS scaffold at: {root}")
    return 0




REQUIRED_FEATURES = [
    "chat_tab",
    "studio_tab",
    "super_agent_swarm_tab",
    "llm_training",
    "autonomous_learning",
    "image_generation",
    "image_editing",
    "audio_generation",
    "audio_editing",
    "video_generation",
    "video_editing",
    "plugins_system",
    "modes_and_mods",
    "addins_support",
]

DEFAULT_NEXT_STEPS = [
    "Run dependency check: doctor --output json",
    "Create/update merged workspace: ultimate-merge --sources ... --output-root merge_output --strategy newest",
    "Run first build prep on merged workspace: first-build-prep --project-root merge_output/merged_project --version 1.0",
    "Generate feature checklist: feature-manifest --version 1.0 --output docs/feature_manifest.json",
    "Implement missing features and mark them in the manifest",
    "Register next version snapshot (for example 1.1, 1.2) after each stable milestone",
]


def list_files_relative(root: Path) -> set[str]:
    out: set[str] = set()
    for dirpath, _, filenames in os.walk(root):
        d = Path(dirpath)
        for fn in filenames:
            out.add((d / fn).relative_to(root).as_posix())
    return out


def cmd_compare_versions(args: argparse.Namespace) -> int:
    vault = Path(args.vault)
    a = vault / args.from_version
    b = vault / args.to_version

    if not a.is_dir() or not b.is_dir():
        print("ERROR: both versions must exist in vault", file=sys.stderr)
        return 2

    a_files = list_files_relative(a)
    b_files = list_files_relative(b)

    added = sorted(b_files - a_files)
    removed = sorted(a_files - b_files)
    common = a_files & b_files

    changed: list[str] = []
    for rel in sorted(common):
        if file_sha256(a / rel) != file_sha256(b / rel):
            changed.append(rel)

    report = {
        "from": args.from_version,
        "to": args.to_version,
        "added_count": len(added),
        "removed_count": len(removed),
        "changed_count": len(changed),
        "added": added[: args.limit],
        "removed": removed[: args.limit],
        "changed": changed[: args.limit],
    }

    if args.output == "json":
        print(json.dumps(report, indent=2))
    else:
        print(f"Compare {args.from_version} -> {args.to_version}")
        print(f"Added: {len(added)}  Removed: {len(removed)}  Changed: {len(changed)}")
        if added:
            print("- Added (sample):")
            for x in added[: args.limit]:
                print(f"  - {x}")
        if removed:
            print("- Removed (sample):")
            for x in removed[: args.limit]:
                print(f"  - {x}")
        if changed:
            print("- Changed (sample):")
            for x in changed[: args.limit]:
                print(f"  - {x}")

    return 0


def cmd_feature_manifest(args: argparse.Namespace) -> int:
    features = REQUIRED_FEATURES.copy()
    if args.extra_feature:
        features.extend(args.extra_feature)

    manifest = {
        "target_version": args.version,
        "generated_utc": f"{dt.datetime.now(dt.UTC):%Y-%m-%d %H:%M:%S}",
        "features": [{"name": f, "required": True, "implemented": False, "notes": ""} for f in features],
        "tabs": [
            {"name": "chat", "required": True, "implemented": False},
            {"name": "studio", "required": True, "implemented": False},
            {"name": "super_agent_swarm", "required": True, "implemented": False},
        ],
        "studio_capabilities": {
            "image": {"generate": False, "edit": False, "preview": False},
            "audio": {"generate": False, "edit": False, "preview": False},
            "video": {"generate": False, "edit": False, "preview": False},
        },
    }

    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(manifest, indent=2))
    print(f"Feature manifest template created: {out}")
    return 0


def cmd_next_steps(args: argparse.Namespace) -> int:
    plan = {
        "current_version": args.version,
        "notes": [
            "A commit id like 84f8bf3 is a saved snapshot in git history.",
            "Run `git log --oneline` to list snapshots and `git show <id>` to inspect one.",
        ],
        "recommended_steps": DEFAULT_NEXT_STEPS,
    }

    if args.output == "json":
        print(json.dumps(plan, indent=2))
        return 0

    print("== What next ==")
    print(f"Current working version: {args.version}")
    print("\nAbout commit IDs:")
    for note in plan["notes"]:
        print(f"- {note}")

    print("\nRecommended next steps:")
    for i, step in enumerate(plan["recommended_steps"], start=1):
        print(f"{i}. {step}")
    return 0

def cmd_first_build_prep(args: argparse.Namespace) -> int:
    project_root = Path(args.project_root)
    if not project_root.exists() or not project_root.is_dir():
        print(f"ERROR: project root not found: {project_root}", file=sys.stderr)
        return 2

    print("== First Build Preparation ==")

    # 1) Backup
    backup_args = argparse.Namespace(
        source=str(project_root),
        backup_root=args.backup_root,
        label=args.backup_label,
    )
    backup_code = cmd_backup(backup_args)

    # 2) Register version snapshot
    reg_args = argparse.Namespace(
        version=args.version,
        source=str(project_root),
        vault=args.vault,
    )
    reg_code = cmd_register_version(reg_args)

    # 3) Save kickoff chat note (optional)
    if args.note:
        chat_args = argparse.Namespace(
            text=args.note,
            file="",
            source="first-build-prep",
            log=args.chat_log,
        )
        chat_code = cmd_save_chat(chat_args)
    else:
        chat_code = 0

    # 4) Preflight
    preflight_args = argparse.Namespace(
        project_root=str(project_root),
        report_dir=args.report_dir,
        output="text",
        skip_tests=args.skip_tests,
        backup_before=False,
        backup_source=str(project_root),
        backup_root=args.backup_root,
        backup_label="preflight",
    )
    preflight_code = cmd_preflight(preflight_args)

    ok = all(code == 0 for code in [backup_code, reg_code, chat_code, preflight_code])
    print("First build prep complete." if ok else "First build prep finished with issues.")
    return 0 if ok else 1

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="AAVA migration toolkit")
    sub = parser.add_subparsers(dest="command", required=True)

    p_bootstrap = sub.add_parser("bootstrap", help="Copy source project into a renamed working folder")
    p_bootstrap.add_argument("--new-name", default="AAVA_Project_vNext")
    p_bootstrap.add_argument("--dest-root", default="/workspace")
    p_bootstrap.add_argument("--sources", nargs="*", help="Optional source candidate list")
    p_bootstrap.set_defaults(func=cmd_bootstrap)

    p_scan = sub.add_parser("deep-scan", help="Deep scan source locations")
    p_scan.add_argument("paths", nargs="*", help="Optional paths to scan")
    p_scan.add_argument("--output", choices=["text", "json"], default="text")
    p_scan.set_defaults(func=cmd_deep_scan)

    p_pdf = sub.add_parser("pdf-scan", help="Scan PDFs for version markers")
    p_pdf.add_argument("--search-root", default=".")
    p_pdf.add_argument("--output", choices=["text", "json"], default="text")
    p_pdf.set_defaults(func=cmd_pdf_scan)

    p_kick = sub.add_parser("kickoff", help="Run bootstrap + scans and write report")
    p_kick.add_argument("--new-name", default="AAVA_Project_vNext")
    p_kick.add_argument("--dest-root", default="/workspace")
    p_kick.add_argument("--fail-on-error", action="store_true", help="Return non-zero if any kickoff step fails")
    p_kick.set_defaults(func=cmd_kickoff)

    p_init = sub.add_parser("init-aiios", help="Initialize AIIOS architecture scaffold")
    p_init.add_argument("--root", default="aiios_workspace")
    p_init.set_defaults(func=cmd_init_aiios)


    p_doctor = sub.add_parser("doctor", help="Check dependencies and optional tools")
    p_doctor.add_argument("--output", choices=["text", "json"], default="text")
    p_doctor.add_argument("--install-optional", action="store_true", help="Attempt to install optional pypdf dependency")
    p_doctor.set_defaults(func=cmd_doctor)

    p_backup = sub.add_parser("backup", help="Create a timestamped backup archive before updates")
    p_backup.add_argument("--source", default=".")
    p_backup.add_argument("--backup-root", default=str(DEFAULT_BACKUP_ROOT))
    p_backup.add_argument("--label", default="")
    p_backup.set_defaults(func=cmd_backup)

    p_ver = sub.add_parser("register-version", help="Store one snapshot per major.minor version")
    p_ver.add_argument("--version", required=True, help="major.minor, e.g. 1.0 or 1.5")
    p_ver.add_argument("--source", default=".")
    p_ver.add_argument("--vault", default=str(DEFAULT_VERSION_VAULT))
    p_ver.set_defaults(func=cmd_register_version)

    p_chat = sub.add_parser("save-chat", help="Append chat records to local JSONL history")
    p_chat.add_argument("--text", default="")
    p_chat.add_argument("--file", default="")
    p_chat.add_argument("--source", default="manual")
    p_chat.add_argument("--log", default=str(DEFAULT_CHAT_LOG))
    p_chat.set_defaults(func=cmd_save_chat)


    p_merge = sub.add_parser("ultimate-merge", help="Merge multiple source trees into one best-of project")
    p_merge.add_argument("--sources", nargs="+", required=True, help="Source directories (Windows or Linux paths)")
    p_merge.add_argument("--output-root", default="merge_output")
    p_merge.add_argument("--strategy", choices=["first", "newest", "largest"], default="newest")
    p_merge.set_defaults(func=cmd_ultimate_merge)


    p_preflight = sub.add_parser("preflight", help="Run dependency check + optional backup + tests before build/launch")
    p_preflight.add_argument("--project-root", default=".")
    p_preflight.add_argument("--report-dir", default="reports")
    p_preflight.add_argument("--output", choices=["text", "json"], default="text")
    p_preflight.add_argument("--skip-tests", action="store_true")
    p_preflight.add_argument("--backup-before", action="store_true")
    p_preflight.add_argument("--backup-source", default=".")
    p_preflight.add_argument("--backup-root", default=str(DEFAULT_BACKUP_ROOT))
    p_preflight.add_argument("--backup-label", default="preflight")
    p_preflight.set_defaults(func=cmd_preflight)


    p_first = sub.add_parser("first-build-prep", help="Run backup + version snapshot + preflight before first build")
    p_first.add_argument("--project-root", default=".")
    p_first.add_argument("--version", default="1.0")
    p_first.add_argument("--backup-root", default=str(DEFAULT_BACKUP_ROOT))
    p_first.add_argument("--backup-label", default="first_build")
    p_first.add_argument("--vault", default=str(DEFAULT_VERSION_VAULT))
    p_first.add_argument("--report-dir", default="reports")
    p_first.add_argument("--chat-log", default=str(DEFAULT_CHAT_LOG))
    p_first.add_argument("--note", default="")
    p_first.add_argument("--skip-tests", action="store_true")
    p_first.set_defaults(func=cmd_first_build_prep)


    p_cmp = sub.add_parser("compare-versions", help="Compare two registered version snapshots")
    p_cmp.add_argument("--vault", default=str(DEFAULT_VERSION_VAULT))
    p_cmp.add_argument("--from-version", required=True)
    p_cmp.add_argument("--to-version", required=True)
    p_cmp.add_argument("--limit", type=int, default=200)
    p_cmp.add_argument("--output", choices=["text", "json"], default="text")
    p_cmp.set_defaults(func=cmd_compare_versions)

    p_feat = sub.add_parser("feature-manifest", help="Generate required feature checklist template")
    p_feat.add_argument("--version", default="1.0")
    p_feat.add_argument("--output", default="docs/feature_manifest.json")
    p_feat.add_argument("--extra-feature", action="append", default=[])
    p_feat.set_defaults(func=cmd_feature_manifest)

    p_next = sub.add_parser("next-steps", help="Show recommended sequence after setup and explain commit IDs")
    p_next.add_argument("--version", default="1.0")
    p_next.add_argument("--output", choices=["text", "json"], default="text")
    p_next.set_defaults(func=cmd_next_steps)

    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
