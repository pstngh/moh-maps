from __future__ import annotations

import hashlib
import importlib.util
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "evidence_loop.py"
SPEC = importlib.util.spec_from_file_location("mohaa_evidence_loop", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
evidence_loop = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(evidence_loop)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class EvidenceLoopTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.map_name = "test_map"
        self.candidate = self.root / "test_map.pk3"
        self._write_pk3(self.candidate, b"bsp-v1")
        self.visual_root = self.root / "visual"
        self.runtime_root = self.root / "runtime"
        self._copy_runtime(self.visual_root, self.candidate)
        self._copy_runtime(self.runtime_root, self.candidate)
        self.visual_engine = self.root / "openmohaa.exe"
        self.bot_engine = self.root / "omohaaded.exe"
        self.visual_engine.write_bytes(b"visual-engine")
        self.bot_engine.write_bytes(b"bot-engine")
        self.screenshots = []
        for index in range(3):
            path = self.visual_root / "home" / "main" / "screenshots" / f"shot{index:04}.tga"
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(f"tga-{index}".encode("ascii"))
            self.screenshots.append(path)
        self.trace = self.root / "bot-trace.jsonl"
        self.trace.write_text(
            "\n".join(
                [
                    '{"bot":"bot1","event":"spawn"}',
                    '{"bot":"bot1","event":"movement"}',
                    '{"bot":"bot1","event":"combat"}',
                    '{"bot":"bot1","event":"death"}',
                    '{"bot":"bot1","event":"respawn"}',
                    '{"bot":"bot1","route":"main_loop","sample":1}',
                    '{"bot":"bot1","route":"main_loop","sample":2}',
                ]
            ) + "\n",
            encoding="utf-8",
        )
        self.visual_log = self.visual_root / "home" / "main" / "qconsole.log"
        self.runtime_log = self.runtime_root / "home" / "main" / "qconsole.log"
        for log in (self.visual_log, self.runtime_log):
            log.parent.mkdir(parents=True, exist_ok=True)
            log.write_text("OpenMoHAA test log\n", encoding="utf-8")
        candidate_sha = sha256(self.candidate)
        self.visual_report = self.root / "visual.json"
        self.runtime_report = self.root / "runtime.json"
        self.plan_path = self.root / "plan.json"
        self.source_map = self.root / "test_map.map"
        self.compiled_bsp = self.root / "test_map.bsp"
        self.compile_log = self.root / "compile.log"
        self.design_report = self.root / "design-report.json"
        self.source_map.write_bytes(b"map-source")
        self.compiled_bsp.write_bytes(b"bsp-v1")
        self.compile_log.write_text("BSP VIS LIGHT complete\n", encoding="utf-8")
        self._write_json(
            self.design_report, {"generated": {"mapSha256": sha256(self.source_map)}}
        )
        self._write_json(
            self.visual_report,
            {
                "mapName": self.map_name,
                "qaRoot": str(self.visual_root),
                "exactPk3Count": 8,
                "candidateSha256": candidate_sha,
                "requestedViews": ["forward", "reverse", "overview"],
                "viewMarkers": [
                    "CODEX_VISUAL_QA forward",
                    "CODEX_VISUAL_QA reverse",
                    "CODEX_VISUAL_QA overview",
                ],
                "screenshotCount": 3,
                "screenshots": [
                    {"path": str(path), "bytes": path.stat().st_size, "sha256": sha256(path)}
                    for path in self.screenshots
                ],
                "scriptErrorCount": 0,
                "log": str(self.visual_log),
            },
        )
        self._write_json(
            self.runtime_report,
            {
                "mapName": self.map_name,
                "qaRoot": str(self.runtime_root),
                "exactPk3Count": 8,
                "candidateSha256": candidate_sha,
                "engineSha256": sha256(self.bot_engine),
                "bspParse": ["BSP file loaded and parsed"],
                "recast": ["Recast navigation mesh(es) generated"],
                "botsEntered": 8,
                "combatEvents": 4,
                "minimumCombatEvents": 3,
                "candidateDiagnostics": [],
                "stockAssetDiagnostics": [],
                "scriptErrorCount": 0,
                "log": str(self.runtime_log),
            },
        )
        self.plan = self._complete_plan()
        self._write_json(self.plan_path, self.plan)

    def tearDown(self) -> None:
        self.temp.cleanup()

    def _write_pk3(self, path: Path, bsp: bytes, *, second_bsp: bool = False) -> None:
        with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_STORED) as archive:
            archive.writestr("maps/dm/test_map.bsp", bsp)
            archive.writestr("maps/dm/test_map.scr", b"main:\nend\n")
            if second_bsp:
                archive.writestr("maps/dm/other.bsp", b"other")

    def _copy_runtime(self, root: Path, candidate: Path) -> None:
        target = root / "base" / "main" / "zz_test_map.pk3"
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(candidate, target)
        for index in range(7):
            (target.parent / f"Pak{index}.pk3").write_bytes(f"retail-{index}".encode("ascii"))

    def _write_json(self, path: Path, value: dict) -> None:
        path.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")

    def _complete_plan(self) -> dict:
        trace_sha = sha256(self.trace)
        candidate_sha = sha256(self.candidate)
        return {
            "schema_version": 1,
            "map_name": self.map_name,
            "expected_bsp_member": "maps/dm/test_map.bsp",
            "build_provenance": {
                "source_map": {
                    "path": str(self.source_map),
                    "sha256": sha256(self.source_map),
                },
                "design_report": {
                    "path": str(self.design_report),
                    "sha256": sha256(self.design_report),
                },
                "compile_log": {
                    "path": str(self.compile_log),
                    "sha256": sha256(self.compile_log),
                },
                "compiled_bsp": {
                    "path": str(self.compiled_bsp),
                    "sha256": sha256(self.compiled_bsp),
                },
            },
            "launch_provenance": {
                "visual": {
                    "engine_path": str(self.visual_engine),
                    "engine_sha256": sha256(self.visual_engine),
                    "arguments": ["+set", "fs_basepath", str(self.visual_root / "base")],
                    "fs_basepath": str(self.visual_root / "base"),
                    "fs_homepath": str(self.visual_root / "home"),
                },
                "bot": {
                    "engine_path": str(self.bot_engine),
                    "engine_sha256": sha256(self.bot_engine),
                    "arguments": ["+set", "fs_basepath", str(self.runtime_root / "base")],
                    "fs_basepath": str(self.runtime_root / "base"),
                    "fs_homepath": str(self.runtime_root / "home"),
                },
            },
            "runtime_diagnostic_classifications": [],
            "required_view_categories": ["player_forward", "player_reverse", "high_angle"],
            "views": [
                {"id": "forward", "categories": ["player_forward"], "perspective": "fixed"},
                {"id": "reverse", "categories": ["player_reverse"], "perspective": "fixed"},
                {"id": "overview", "categories": ["high_angle"], "perspective": "fixed"},
            ],
            "visual_review": {
                "reviewer_kind": "codex_visual",
                "candidate_sha256": candidate_sha,
                "views": [
                    {
                        "id": view_id,
                        "screenshot_sha256": sha256(path),
                        "reviewed": True,
                        "blocking_defects": [],
                        "observations": [],
                    }
                    for view_id, path in zip(
                        ["forward", "reverse", "overview"], self.screenshots
                    )
                ],
            },
            "bot_evidence": {
                "expected_bot_count": 8,
                "required_routes": ["main_loop"],
                "event_observations": [
                    {
                        "event": event,
                        "source_path": str(self.trace),
                        "source_sha256": trace_sha,
                        "needle": f'"event":"{event}"',
                        "matches": 1,
                    }
                    for event in ["spawn", "movement", "combat", "death", "respawn"]
                ],
                "route_observations": [
                    {
                        "route_id": "main_loop",
                        "method": "instrumented_positions",
                        "source_path": str(self.trace),
                        "source_sha256": trace_sha,
                        "needle": '"route":"main_loop"',
                        "sample_count": 2,
                        "unique_bots": 1,
                    }
                ],
            },
        }

    def audit(self) -> dict:
        return evidence_loop.build_audit(
            self.candidate,
            self.visual_report,
            self.runtime_report,
            self.plan_path,
        )

    def test_complete_exact_hash_evidence_passes_non_human_gates(self) -> None:
        report = self.audit()
        self.assertTrue(report["technical_ready_for_human_review"])
        self.assertFalse(report["promotion_allowed"])
        self.assertEqual(report["gates"]["human_acceptance"]["status"], "open")
        self.assertEqual(report["scores"]["exact_identity"], 100)
        self.assertFalse(evidence_loop.strict_failure(report))

    def test_runtime_copy_hash_mismatch_fails_identity(self) -> None:
        mismatched = self.root / "mismatch.pk3"
        self._write_pk3(mismatched, b"different-bsp")
        shutil.copyfile(
            mismatched,
            self.visual_root / "base" / "main" / "zz_test_map.pk3",
        )
        report = self.audit()
        self.assertEqual(
            report["gates"]["visual_runtime_package_identity"]["status"], "fail"
        )
        self.assertFalse(report["technical_ready_for_human_review"])
        self.assertEqual(report["gates"]["fixed_view_capture"]["status"], "fail")
        self.assertEqual(report["scores"]["capture_integrity_and_coverage"], 100)

    def test_unexpected_loose_bsp_fails_runtime_identity(self) -> None:
        loose = self.visual_root / "home" / "main" / "maps" / "dm" / "test_map.bsp"
        loose.parent.mkdir(parents=True, exist_ok=True)
        loose.write_bytes(b"masking-bsp")
        report = self.audit()
        self.assertEqual(
            report["gates"]["visual_runtime_package_identity"]["status"], "fail"
        )
        self.assertIn(
            "unexpected loose runtime files",
            report["gates"]["visual_runtime_package_identity"]["detail"],
        )

    def test_tampered_engine_fails_launch_provenance(self) -> None:
        self.visual_engine.write_bytes(b"tampered-engine")
        report = self.audit()
        self.assertEqual(report["gates"]["launch_provenance"]["status"], "fail")
        self.assertFalse(report["technical_ready_for_human_review"])
        self.assertIn(
            "engine hash does not match",
            report["gates"]["launch_provenance"]["detail"],
        )

    def test_raw_log_overrides_underreported_json_diagnostics(self) -> None:
        self.runtime_log.write_text(
            "global/bot_run.scr is not properly loaded\n",
            encoding="utf-8",
        )
        report = self.audit()
        self.assertEqual(report["gates"]["runtime_load"]["status"], "pass")
        self.assertEqual(report["gates"]["raw_runtime_diagnostics"]["status"], "fail")
        self.assertIn("not properly loaded", report["gates"]["raw_runtime_diagnostics"]["detail"])
        self.assertFalse(report["technical_ready_for_human_review"])

    def test_bot_observation_must_exist_in_hash_linked_source(self) -> None:
        death = next(
            item for item in self.plan["bot_evidence"]["event_observations"]
            if item["event"] == "death"
        )
        death["needle"] = '"event":"not-present"'
        self._write_json(self.plan_path, self.plan)
        report = self.audit()
        self.assertEqual(report["gates"]["bot_lifecycle"]["status"], "fail")
        self.assertIn("below declared matches", report["gates"]["bot_lifecycle"]["detail"])

    def test_runtime_claims_do_not_pass_when_runtime_identity_fails(self) -> None:
        mismatched = self.root / "mismatch.pk3"
        self._write_pk3(mismatched, b"different-bsp")
        shutil.copyfile(
            mismatched,
            self.runtime_root / "base" / "main" / "zz_test_map.pk3",
        )
        report = self.audit()
        self.assertEqual(report["gates"]["bot_runtime_package_identity"]["status"], "fail")
        self.assertEqual(report["gates"]["runtime_load"]["status"], "fail")
        self.assertEqual(report["gates"]["bot_entry_and_combat"]["status"], "fail")
        self.assertEqual(report["scores"]["runtime_and_bot_activity"], 0)
        self.assertIn(
            "cannot be attributed",
            report["gates"]["bot_entry_and_combat"]["detail"],
        )

    def test_tampered_compiled_bsp_fails_build_provenance(self) -> None:
        self.compiled_bsp.write_bytes(b"tampered-bsp")
        report = self.audit()
        self.assertEqual(report["gates"]["build_provenance"]["status"], "fail")
        self.assertFalse(report["technical_ready_for_human_review"])
        self.assertIn(
            "compiled BSP",
            report["gates"]["build_provenance"]["detail"],
        )

    def test_dynamic_follow_view_does_not_satisfy_fixed_category(self) -> None:
        self.plan["views"][0]["perspective"] = "spectator_follow"
        self._write_json(self.plan_path, self.plan)
        report = self.audit()
        self.assertEqual(report["gates"]["fixed_view_capture"]["status"], "fail")
        self.assertTrue(any("dynamic/follow" in item for item in report["open_items"]))

    def test_combat_activity_does_not_prove_lifecycle_or_routes(self) -> None:
        del self.plan["bot_evidence"]
        self._write_json(self.plan_path, self.plan)
        report = self.audit()
        self.assertEqual(report["gates"]["bot_entry_and_combat"]["status"], "pass")
        self.assertEqual(report["gates"]["bot_lifecycle"]["status"], "open")
        self.assertEqual(report["gates"]["bot_route_coverage"]["status"], "open")
        self.assertIsNone(report["scores"]["bot_lifecycle_and_route_evidence"])

    def test_multiple_bsp_members_fail_unambiguous_package_gate(self) -> None:
        self._write_pk3(self.candidate, b"bsp-v2", second_bsp=True)
        report = self.audit()
        self.assertEqual(report["gates"]["candidate_package_identity"]["status"], "fail")
        self.assertFalse(report["promotion_allowed"])

    def test_compare_reports_never_promotes(self) -> None:
        before = self.audit()
        before["scores"]["semantic_visual_review_completeness"] = 50
        before["gates"]["semantic_visual_review"]["status"] = "open"
        after = self.audit()
        before_path = self.root / "before.json"
        after_path = self.root / "after.json"
        self._write_json(before_path, before)
        self._write_json(after_path, after)
        comparison = evidence_loop.compare_reports(before_path, after_path)
        self.assertTrue(comparison["bounded_evidence_improvement"])
        self.assertFalse(comparison["promotion_allowed"])
        self.assertEqual(comparison["acceptance_status"], "requires_explicit_user_approval")

    def test_cli_strict_exit_codes_are_zero_or_two(self) -> None:
        command = [
            sys.executable,
            str(SCRIPT),
            "audit",
            "--candidate-pk3",
            str(self.candidate),
            "--visual-report",
            str(self.visual_report),
            "--runtime-report",
            str(self.runtime_report),
            "--evidence-plan",
            str(self.plan_path),
            "--strict",
        ]
        complete = subprocess.run(
            command,
            check=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
        )
        self.assertEqual(complete.returncode, 0, complete.stderr)
        del self.plan["bot_evidence"]
        self._write_json(self.plan_path, self.plan)
        incomplete = subprocess.run(
            command,
            check=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
        )
        self.assertEqual(incomplete.returncode, 2, incomplete.stderr)


if __name__ == "__main__":
    unittest.main()
