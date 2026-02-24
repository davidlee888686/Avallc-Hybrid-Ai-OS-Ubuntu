import argparse
import json
import tempfile
import unittest
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path

from tools import aava_migration as am


class TestPathNormalization(unittest.TestCase):
    def test_windows_path_maps_to_mnt(self):
        self.assertEqual(am.normalize_windows_path(r"C:\Users\David\Downloads"), Path("/mnt/c/Users/David/Downloads"))

    def test_non_windows_path_unchanged(self):
        self.assertEqual(am.normalize_windows_path("/workspace/demo"), Path("/workspace/demo"))


class TestIterators(unittest.TestCase):
    def test_iter_pdfs_and_key_files_and_repos(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "docs").mkdir()
            (root / "docs" / "one.PDF").write_text("x")
            (root / "nested").mkdir()
            (root / "nested" / "two.pdf").write_text("x")
            (root / "nested" / "README.md").write_text("hello")
            (root / "project" / ".git").mkdir(parents=True)

            self.assertEqual(len(list(am.iter_pdfs(root))), 2)
            self.assertTrue(any(p.name.lower() == "readme.md" for p in am.iter_key_files(root)))
            repos = list(am.iter_repo_roots(root))
            self.assertEqual(len(repos), 1)
            self.assertEqual(repos[0].name, "project")


class TestInitScaffold(unittest.TestCase):
    def test_init_aiios_creates_scaffold(self):
        with tempfile.TemporaryDirectory() as td:
            args = type("Args", (), {"root": str(Path(td) / "aiios_workspace")})()
            code = am.cmd_init_aiios(args)
            self.assertEqual(code, 0)
            root = Path(args.root)
            self.assertTrue((root / "control_plane" / "policy").is_dir())
            self.assertTrue((root / "execution_plane" / "adapters" / "windows").is_dir())
            self.assertTrue((root / "configs" / "system_profile.example.yaml").is_file())


class TestValidationAndOutput(unittest.TestCase):
    def test_safe_project_name(self):
        self.assertTrue(am.is_safe_project_name("AAVA_Project_vNext-1.0"))
        self.assertFalse(am.is_safe_project_name("../bad"))

    def test_semver2(self):
        self.assertTrue(am.is_semver2("1.0"))
        self.assertTrue(am.is_semver2("10.5"))
        self.assertFalse(am.is_semver2("1"))
        self.assertFalse(am.is_semver2("1.0.0"))

    def test_dependency_status_shape(self):
        status = am.collect_dependency_status()
        self.assertIn("tools", status)
        self.assertIn("python_modules", status)
        self.assertIn("python3", status["tools"])

    def test_deep_scan_json_output(self):
        args = argparse.Namespace(paths=["/definitely_missing_path"], output="json")
        buf = StringIO()
        with redirect_stdout(buf):
            code = am.cmd_deep_scan(args)
        self.assertEqual(code, 0)
        payload = json.loads(buf.getvalue())
        self.assertIn("targets", payload)
        self.assertEqual(payload["targets"][0]["status"], "missing")


class TestBackupVersionAndChat(unittest.TestCase):
    def test_backup_register_and_chat(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            src = root / "src"
            src.mkdir()
            (src / "a.txt").write_text("hello")

            backup_root = root / "bkp"
            code = am.cmd_backup(argparse.Namespace(source=str(src), backup_root=str(backup_root), label="preupdate"))
            self.assertEqual(code, 0)
            self.assertTrue(any(p.suffixes[-2:] == [".tar", ".gz"] for p in backup_root.iterdir()))

            vault = root / "versions"
            code = am.cmd_register_version(argparse.Namespace(version="1.0", source=str(src), vault=str(vault)))
            self.assertEqual(code, 0)
            self.assertTrue((vault / "1.0" / "a.txt").is_file())
            manifest = json.loads((vault / "manifest.json").read_text())
            self.assertIn("1.0", manifest["versions"])

            chat_log = root / "chats" / "history.jsonl"
            code = am.cmd_save_chat(argparse.Namespace(text="hello chat", file="", source="unit-test", log=str(chat_log)))
            self.assertEqual(code, 0)
            lines = chat_log.read_text().strip().splitlines()
            self.assertEqual(len(lines), 1)
            record = json.loads(lines[0])
            self.assertEqual(record["source"], "unit-test")


class TestUltimateMerge(unittest.TestCase):
    def test_ultimate_merge_combines_and_reports(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            s1 = root / "s1"
            s2 = root / "s2"
            s1.mkdir(); s2.mkdir()
            (s1 / "common.txt").write_text("old")
            (s2 / "common.txt").write_text("newer")
            (s1 / "only1.txt").write_text("a")
            (s2 / "only2.txt").write_text("b")

            out = root / "out"
            args = argparse.Namespace(
                sources=[str(s1), str(s2)],
                output_root=str(out),
                strategy="newest",
            )
            code = am.cmd_ultimate_merge(args)
            self.assertEqual(code, 0)
            merged = out / "merged_project"
            self.assertTrue((merged / "only1.txt").is_file())
            self.assertTrue((merged / "only2.txt").is_file())
            self.assertTrue((out / "merge_report" / "merge_report.json").is_file())


class TestPreflight(unittest.TestCase):
    def test_preflight_generates_report(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            args = argparse.Namespace(
                project_root=str(root),
                report_dir=str(root / "reports"),
                output="json",
                skip_tests=True,
                backup_before=False,
                backup_source=str(root),
                backup_root=str(root / "backups"),
                backup_label="preflight",
            )
            code = am.cmd_preflight(args)
            self.assertEqual(code, 0)
            reports = list((root / "reports").glob("preflight_*.json"))
            self.assertTrue(reports)


class TestFirstBuildPrep(unittest.TestCase):
    def test_first_build_prep_runs(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "main.txt").write_text("x")
            args = argparse.Namespace(
                project_root=str(root),
                version="1.0",
                backup_root=str(root / "backups"),
                backup_label="first_build",
                vault=str(root / "versions"),
                report_dir=str(root / "reports"),
                chat_log=str(root / "chats" / "history.jsonl"),
                note="prep note",
                skip_tests=True,
            )
            code = am.cmd_first_build_prep(args)
            self.assertEqual(code, 0)
            self.assertTrue((root / "versions" / "1.0").is_dir())
            self.assertTrue(any((root / "backups").iterdir()))
            self.assertTrue(any((root / "reports").glob("preflight_*.json")))


class TestVersionCompareAndFeatureManifest(unittest.TestCase):
    def test_compare_versions_and_feature_manifest(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            vault = root / "versions"
            (vault / "1.0").mkdir(parents=True)
            (vault / "1.1").mkdir(parents=True)
            (vault / "1.0" / "a.txt").write_text("old")
            (vault / "1.1" / "a.txt").write_text("new")
            (vault / "1.1" / "b.txt").write_text("b")

            cmp_args = argparse.Namespace(vault=str(vault), from_version="1.0", to_version="1.1", limit=50, output="json")
            buf = StringIO()
            with redirect_stdout(buf):
                code = am.cmd_compare_versions(cmp_args)
            self.assertEqual(code, 0)
            payload = json.loads(buf.getvalue())
            self.assertGreaterEqual(payload["added_count"], 1)
            self.assertGreaterEqual(payload["changed_count"], 1)

            manifest_path = root / "feature_manifest.json"
            feat_args = argparse.Namespace(version="1.1", output=str(manifest_path), extra_feature=["custom_tab"])
            code = am.cmd_feature_manifest(feat_args)
            self.assertEqual(code, 0)
            data = json.loads(manifest_path.read_text())
            self.assertEqual(data["target_version"], "1.1")
            names = [f["name"] for f in data["features"]]
            self.assertIn("custom_tab", names)


class TestNextSteps(unittest.TestCase):
    def test_next_steps_json(self):
        args = argparse.Namespace(version="1.0", output="json")
        buf = StringIO()
        with redirect_stdout(buf):
            code = am.cmd_next_steps(args)
        self.assertEqual(code, 0)
        payload = json.loads(buf.getvalue())
        self.assertIn("recommended_steps", payload)
        self.assertGreaterEqual(len(payload["recommended_steps"]), 1)


class TestStartHere(unittest.TestCase):
    def test_start_here_fresh_install_json(self):
        args = argparse.Namespace(mode="fresh-install", output="json")
        buf = StringIO()
        with redirect_stdout(buf):
            code = am.cmd_start_here(args)
        self.assertEqual(code, 0)
        payload = json.loads(buf.getvalue())
        self.assertEqual(payload["mode"], "fresh-install")
        self.assertTrue(any("git clone https://github.com/davidlee888686/Avallc-Hybrid-Ai-OS-Ubuntu.git" in s for s in payload["steps"]))


class TestSetupEnv(unittest.TestCase):
    def test_setup_env_json(self):
        args = argparse.Namespace(apply=False, output="json")
        buf = StringIO()
        with redirect_stdout(buf):
            code = am.cmd_setup_env(args)
        self.assertEqual(code, 0)
        payload = json.loads(buf.getvalue())
        self.assertIn("platform_family", payload)
        self.assertIn("dependency_status", payload)
        self.assertIn("planned_commands", payload)


class TestParser(unittest.TestCase):
    def test_parser_includes_doctor(self):
        parser = am.build_parser()
        with self.assertRaises(SystemExit) as cm:
            parser.parse_args(["compare-versions", "--help"])
        self.assertEqual(cm.exception.code, 0)

    def test_parser_includes_setup_env(self):
        parser = am.build_parser()
        args = parser.parse_args(["setup-env", "--output", "json"])
        self.assertEqual(args.command, "setup-env")


if __name__ == "__main__":
    unittest.main()
