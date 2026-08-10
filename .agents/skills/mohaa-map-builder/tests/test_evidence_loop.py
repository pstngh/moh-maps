from __future__ import annotations

import hashlib
import importlib.util
import json
import os
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
        self.route_trace = self.root / "bot-routes.jsonl"
        self.route_trace.write_text(
            "\n".join(
                [
                    '{"bot":"bot1","route":"main_loop","sample":1}',
                    '{"bot":"bot1","route":"main_loop","sample":2}',
                ]
            ) + "\n",
            encoding="utf-8",
        )
        self.visual_log = self.visual_root / "home" / "main" / "qconsole.log"
        self.runtime_log = self.runtime_root / "home" / "main" / "qconsole.log"
        for label, log in (
            ("visual", self.visual_log),
            ("bot", self.runtime_log),
        ):
            log.parent.mkdir(parents=True, exist_ok=True)
            lines = [f"OpenMoHAA {label} test log"]
            if label == "bot":
                lines.extend(
                    f"bot{index} has entered the battle" for index in range(1, 9)
                )
                lines.extend(
                    (
                        "bot1 was rifled by bot2",
                        "bot2 was machine-gunned by bot3",
                        "bot3 was hunted down by bot4",
                        "bot4 was perforated by bot5",
                    )
                )
                lines.append("BSP file loaded and parsed in 0.100 seconds")
                lines.append("Recast navigation mesh(es) generated in 0.200 seconds")
            log.write_text("\n".join(lines) + "\n", encoding="utf-8")
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
                "bspParse": ["BSP file loaded and parsed in 0.100 seconds"],
                "recast": ["Recast navigation mesh(es) generated in 0.200 seconds"],
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

    def _write_bundle_manifest(self, destination: Path, manifest: dict) -> None:
        manifest["object_count"] = len(
            {item["object"] for item in manifest["artifacts"]}
        )
        payload = (json.dumps(manifest, indent=2) + "\n").encode("utf-8")
        (destination / "manifest.json").write_bytes(payload)
        manifest_sha = hashlib.sha256(payload).hexdigest()
        (destination / "manifest.sha256").write_text(
            f"{manifest_sha}  manifest.json\n", encoding="ascii"
        )

    def _write_bundle_audit(
        self,
        destination: Path,
        manifest: dict,
        audit: dict,
    ) -> None:
        audit_entry = next(
            item for item in manifest["artifacts"] if item["role"] == "audit"
        )
        old_object = audit_entry["object"]
        payload = (json.dumps(audit, indent=2) + "\n").encode("utf-8")
        digest = hashlib.sha256(payload).hexdigest()
        relative = f"objects/sha256/{digest}"
        (destination / relative).write_bytes(payload)
        audit_entry.update(
            {
                "bytes": len(payload),
                "sha256": digest,
                "object": relative,
            }
        )
        manifest["audit_artifact_sha256"] = digest
        referenced = {item["object"] for item in manifest["artifacts"]}
        old_path = destination / old_object
        if old_object not in referenced:
            old_path.unlink()
        self._write_bundle_manifest(destination, manifest)

    def _rewrite_bundle_visual_report(
        self,
        source: Path,
        destination: Path,
        variant: str,
    ) -> None:
        shutil.copytree(source, destination)
        manifest_path = destination / "manifest.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        by_role = {item["role"]: item for item in manifest["artifacts"]}
        visual_entry = by_role["report:visual"]
        old_visual_object = visual_entry["object"]
        visual = json.loads(
            (destination / old_visual_object).read_text(encoding="utf-8")
        )
        if variant == "raw-log":
            runtime_entry = by_role["report:runtime"]
            runtime = json.loads(
                (destination / runtime_entry["object"]).read_text(encoding="utf-8")
            )
            visual["log"] = runtime["log"]
        elif variant == "runtime-log":
            runtime_entry = by_role["report:runtime"]
            runtime = json.loads(
                (destination / runtime_entry["object"]).read_text(encoding="utf-8")
            )
            visual["runtimeLog"] = runtime["log"]
        elif variant == "map-name":
            visual["mapName"] = "fabricated_map"
        elif variant == "candidate-hash":
            visual["candidateSha256"] = "0" * 64
        elif variant == "engine-hash":
            visual["engineSha256"] = by_role["engine:bot"]["sha256"]
        elif variant == "engine-path":
            visual["enginePath"] = str(self.bot_engine)
        elif variant == "arguments":
            visual["arguments"] = ["+map", "dm/fabricated"]
        elif variant == "fs-basepath":
            visual["fsBasepath"] = str(self.runtime_root / "base")
        elif variant == "fs-homepath":
            visual["fsHomepath"] = str(self.runtime_root / "home")
        elif variant == "first-screenshot":
            visual["screenshots"][0] = dict(visual["screenshots"][1])
        elif variant == "runtime-package":
            visual["runtimePackageSha256"] = "0" * 64
        else:
            self.fail(f"unsupported visual-report variant: {variant}")

        visual_payload = (json.dumps(visual, indent=2) + "\n").encode("utf-8")
        visual_sha = hashlib.sha256(visual_payload).hexdigest()
        visual_object = f"objects/sha256/{visual_sha}"
        (destination / visual_object).write_bytes(visual_payload)
        visual_entry.update(
            {
                "bytes": len(visual_payload),
                "sha256": visual_sha,
                "object": visual_object,
            }
        )
        if old_visual_object not in {
            item["object"] for item in manifest["artifacts"]
        }:
            (destination / old_visual_object).unlink()

        audit_entry = by_role["audit"]
        audit = json.loads(
            (destination / audit_entry["object"]).read_text(encoding="utf-8")
        )
        audit["inputs"]["visual_report"].update(
            {"bytes": len(visual_payload), "sha256": visual_sha}
        )
        indexed_visual = next(
            item
            for item in audit["materialized_roles"]
            if item["role"] == "report:visual"
        )
        indexed_visual.update(
            {"bytes": len(visual_payload), "sha256": visual_sha}
        )
        self._write_bundle_audit(destination, manifest, audit)

    def _rewrite_bundle_runtime_report(
        self,
        source: Path,
        destination: Path,
        variant: str,
    ) -> None:
        shutil.copytree(source, destination)
        manifest_path = destination / "manifest.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        by_role = {item["role"]: item for item in manifest["artifacts"]}
        runtime_entry = by_role["report:runtime"]
        old_runtime_object = runtime_entry["object"]
        runtime = json.loads(
            (destination / old_runtime_object).read_text(encoding="utf-8")
        )
        if variant == "map-name":
            runtime["mapName"] = "fabricated_map"
        elif variant == "candidate-hash":
            runtime["candidateSha256"] = "0" * 64
        elif variant == "raw-log":
            visual_entry = by_role["report:visual"]
            visual = json.loads(
                (destination / visual_entry["object"]).read_text(encoding="utf-8")
            )
            runtime["log"] = visual["log"]
        elif variant == "runtime-package":
            runtime["runtimePackageSha256"] = "0" * 64
        elif variant == "engine-hash":
            runtime["engineSha256"] = "0" * 64
        elif variant in {"bot-activity", "bot-activity-coordinated"}:
            runtime["botsEntered"] = 999
            runtime["combatEvents"] = 999
            runtime["minimumCombatEvents"] = 999
        elif variant == "combat-threshold":
            runtime["minimumCombatEvents"] = 999
        elif variant in {
            "combat-threshold-zero",
            "combat-threshold-bool",
            "combat-threshold-string",
        }:
            runtime["minimumCombatEvents"] = {
                "combat-threshold-zero": 0,
                "combat-threshold-bool": True,
                "combat-threshold-string": "3",
            }[variant]
        elif variant == "runtime-load-observations":
            runtime["bspParse"] = []
            runtime["recast"] = []
        elif variant == "runtime-load-fabricated":
            runtime["bspParse"] = ["fabricated BSP observation"]
            runtime["recast"] = ["fabricated Recast observation"]
        elif variant == "runtime-script-error":
            runtime["scriptErrorCount"] = 1
        else:
            self.fail(f"unsupported runtime-report variant: {variant}")

        runtime_payload = (json.dumps(runtime, indent=2) + "\n").encode("utf-8")
        runtime_sha = hashlib.sha256(runtime_payload).hexdigest()
        runtime_object = f"objects/sha256/{runtime_sha}"
        (destination / runtime_object).write_bytes(runtime_payload)
        runtime_entry.update(
            {
                "bytes": len(runtime_payload),
                "sha256": runtime_sha,
                "object": runtime_object,
            }
        )
        if old_runtime_object not in {
            item["object"] for item in manifest["artifacts"]
        }:
            (destination / old_runtime_object).unlink()

        audit_entry = by_role["audit"]
        audit = json.loads(
            (destination / audit_entry["object"]).read_text(encoding="utf-8")
        )
        if variant == "bot-activity-coordinated":
            audit["bot_activity"].update(
                {
                    "bots_entered": 999,
                    "combat_events": 999,
                    "minimum_combat_events": 999,
                }
            )
        elif variant == "combat-threshold":
            audit["bot_activity"]["minimum_combat_events"] = 999
        elif variant in {
            "combat-threshold-zero",
            "combat-threshold-bool",
            "combat-threshold-string",
        }:
            audit["bot_activity"]["minimum_combat_events"] = runtime[
                "minimumCombatEvents"
            ]
        elif variant == "runtime-load-observations":
            audit["runtime"]["bsp_parse_observations"] = 0
            audit["runtime"]["recast_observations"] = 0
        audit["inputs"]["runtime_report"].update(
            {"bytes": len(runtime_payload), "sha256": runtime_sha}
        )
        indexed_runtime = next(
            item
            for item in audit["materialized_roles"]
            if item["role"] == "report:runtime"
        )
        indexed_runtime.update(
            {"bytes": len(runtime_payload), "sha256": runtime_sha}
        )
        self._write_bundle_audit(destination, manifest, audit)

    def _rewrite_bundle_evidence_plan(
        self,
        source: Path,
        destination: Path,
        *,
        expected_bot_count: int | None = None,
        map_name: str | None = None,
        expected_bsp_member: str | None = None,
        clear_blocking_defects: bool = False,
        required_view_category: str | None = None,
    ) -> None:
        shutil.copytree(source, destination)
        manifest_path = destination / "manifest.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        by_role = {item["role"]: item for item in manifest["artifacts"]}
        plan_entry = by_role["report:evidence_plan"]
        old_plan_object = plan_entry["object"]
        plan = json.loads(
            (destination / old_plan_object).read_text(encoding="utf-8")
        )
        if expected_bot_count is not None:
            plan["bot_evidence"]["expected_bot_count"] = expected_bot_count
        if map_name is not None:
            plan["map_name"] = map_name
        if expected_bsp_member is not None:
            plan["expected_bsp_member"] = expected_bsp_member
        if clear_blocking_defects:
            for view in plan["visual_review"]["views"]:
                view["blocking_defects"] = []
        if required_view_category is not None:
            plan["required_view_categories"].append(required_view_category)

        plan_payload = (json.dumps(plan, indent=2) + "\n").encode("utf-8")
        plan_sha = hashlib.sha256(plan_payload).hexdigest()
        plan_object = f"objects/sha256/{plan_sha}"
        (destination / plan_object).write_bytes(plan_payload)
        plan_entry.update(
            {
                "bytes": len(plan_payload),
                "sha256": plan_sha,
                "object": plan_object,
            }
        )
        if old_plan_object not in {
            item["object"] for item in manifest["artifacts"]
        }:
            (destination / old_plan_object).unlink()

        audit_entry = by_role["audit"]
        audit = json.loads(
            (destination / audit_entry["object"]).read_text(encoding="utf-8")
        )
        audit["inputs"]["evidence_plan"].update(
            {"bytes": len(plan_payload), "sha256": plan_sha}
        )
        indexed_plan = next(
            item
            for item in audit["materialized_roles"]
            if item["role"] == "report:evidence_plan"
        )
        indexed_plan.update({"bytes": len(plan_payload), "sha256": plan_sha})
        self._write_bundle_audit(destination, manifest, audit)

    def _substitute_bundle_role(
        self,
        source: Path,
        destination: Path,
        target_role: str,
        donor_role: str,
    ) -> None:
        shutil.copytree(source, destination)
        manifest_path = destination / "manifest.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        by_role = {item["role"]: item for item in manifest["artifacts"]}
        target = by_role[target_role]
        donor = by_role[donor_role]
        old_object = target["object"]
        for key in ("sha256", "bytes", "object"):
            target[key] = donor[key]
        referenced = {item["object"] for item in manifest["artifacts"]}
        old_path = destination / old_object
        if old_object not in referenced:
            old_path.unlink()
        self._write_bundle_manifest(destination, manifest)

    def _complete_plan(self) -> dict:
        trace_sha = sha256(self.trace)
        route_trace_sha = sha256(self.route_trace)
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
                        "source_path": str(self.route_trace),
                        "source_sha256": route_trace_sha,
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

    def test_error_substrings_inside_identifiers_are_not_diagnostics(self) -> None:
        benign_lines = [
            "Loaded symbol alGetError (00007FFCC86089A0)",
            "Loaded symbol curl_easy_strerror (0x00007FFD23AC13D0)",
            "GL_EXTENSIONS: GL_KHR_no_error GL_AMD_debug_output",
            "Cvar_Set2: ter_error 4",
            "Any SetCurrentTiki errors means that tiki was not prefetched",
            'serverCommand: 2 : cs 1749 "UnknownAmmo"',
            'serverCommand: 26 : cs 1758 "Unknown Item"',
        ]
        for log in (self.visual_log, self.runtime_log):
            log.write_text("\n".join(benign_lines) + "\n", encoding="utf-8")
        report = self.audit()
        self.assertEqual(report["gates"]["raw_runtime_diagnostics"]["status"], "pass")
        self.assertEqual(report["raw_logs"]["visual"]["diagnostic_count"], 0)
        self.assertEqual(report["raw_logs"]["bot"]["diagnostic_count"], 0)

    def test_standalone_error_word_remains_a_diagnostic(self) -> None:
        self.visual_log.write_text(
            "LOCALIZATION ERROR: untranslated key\n",
            encoding="utf-8",
        )
        report = self.audit()
        self.assertEqual(report["gates"]["raw_runtime_diagnostics"]["status"], "open")
        self.assertIn(
            "LOCALIZATION ERROR",
            report["gates"]["raw_runtime_diagnostics"]["detail"],
        )

    def test_explicit_warning_invalid_corruption_and_not_found_are_diagnostics(self) -> None:
        diagnostic_lines = [
            "WARNING: shader has lightmap but no lightmap stage!",
            "CM_AddFacetBevels... invalid bevel",
            "Box data is corrupted for allied_pilot.skd",
            "R_LevelMarksLoad: maps/dm/test_map.dcl not found",
        ]
        self.visual_log.write_text(
            "\n".join(diagnostic_lines) + "\n", encoding="utf-8"
        )
        report = self.audit()
        self.assertEqual(report["gates"]["raw_runtime_diagnostics"]["status"], "open")
        self.assertEqual(report["raw_logs"]["visual"]["diagnostic_count"], 4)

    def test_repeated_timestamped_diagnostics_are_grouped_with_counts(self) -> None:
        literal = "WARNING: shader has lightmap but no lightmap stage!"
        self.visual_log.write_text(
            "\n".join(
                [
                    f"[2026-08-10 11:27:4{index} UTC-5.000] {literal}"
                    for index in range(3)
                ]
            )
            + "\n",
            encoding="utf-8",
        )
        report = self.audit()
        raw = report["raw_logs"]["visual"]
        self.assertEqual(raw["diagnostic_count"], 3)
        self.assertEqual(raw["unique_diagnostic_count"], 1)
        self.assertEqual(raw["diagnostic_groups"], [{"literal": literal, "count": 3}])
        gate_detail = report["gates"]["raw_runtime_diagnostics"]["detail"]
        self.assertEqual(gate_detail.count(literal), 1)
        self.assertIn("(3 occurrences)", gate_detail)

    def test_materialized_bundle_is_deterministic_and_verifiable(self) -> None:
        first = self.root / "bundle-first"
        second = self.root / "bundle-second"
        first_manifest = evidence_loop.materialize_evidence_bundle(
            self.candidate,
            self.visual_report,
            self.runtime_report,
            self.plan_path,
            first,
        )
        second_manifest = evidence_loop.materialize_evidence_bundle(
            self.candidate,
            self.visual_report,
            self.runtime_report,
            self.plan_path,
            second,
        )
        self.assertEqual(first_manifest, second_manifest)
        self.assertEqual(
            (first / "manifest.json").read_bytes(),
            (second / "manifest.json").read_bytes(),
        )
        self.assertEqual(
            first_manifest["candidate_sha256"], sha256(self.candidate)
        )
        self.assertEqual(first_manifest["audit_scorer_sha256"], sha256(SCRIPT))
        self.assertFalse(first_manifest["promotion_allowed"])
        roles = {item["role"] for item in first_manifest["artifacts"]}
        self.assertTrue(
            {
                "candidate",
                "report:visual",
                "report:runtime",
                "report:evidence_plan",
                "raw_log:visual",
                "raw_log:bot",
                "runtime_package:visual",
                "runtime_package:bot",
                "build:source_map",
                "build:design_report",
                "build:compile_log",
                "build:compiled_bsp",
                "engine:visual",
                "engine:bot",
                "screenshot:000:forward",
                "screenshot:001:reverse",
                "screenshot:002:overview",
                "audit",
                "scorer",
            }.issubset(roles)
        )
        verification = evidence_loop.verify_evidence_bundle(first)
        self.assertTrue(verification["valid"])
        self.assertEqual(
            verification["artifact_count"],
            len(first_manifest["artifacts"]),
        )
        audit_entry = next(
            item for item in first_manifest["artifacts"] if item["role"] == "audit"
        )
        audit = json.loads((first / audit_entry["object"]).read_text(encoding="utf-8"))
        indexed_roles = {
            item["role"] for item in audit["materialized_roles"]
        }
        self.assertEqual(indexed_roles, roles - {"audit"})
        scorer_record = next(
            item for item in audit["materialized_roles"] if item["role"] == "scorer"
        )
        self.assertEqual(scorer_record["sha256"], sha256(SCRIPT))

    def test_bundle_verification_rejects_hash_valid_cross_role_substitutions(self) -> None:
        source = self.root / "bundle-source"
        evidence_loop.materialize_evidence_bundle(
            self.candidate,
            self.visual_report,
            self.runtime_report,
            self.plan_path,
            source,
        )
        substitutions = (
            ("report:visual", "report:runtime"),
            ("raw_log:visual", "raw_log:bot"),
            ("screenshot:000:forward", "screenshot:001:reverse"),
            ("engine:visual", "engine:bot"),
            ("build:source_map", "build:design_report"),
            ("bot_source:event:movement", "bot_source:route_id:main_loop"),
        )
        for index, (target_role, donor_role) in enumerate(substitutions):
            with self.subTest(role=target_role):
                destination = self.root / f"bundle-substituted-{index}"
                self._substitute_bundle_role(
                    source,
                    destination,
                    target_role,
                    donor_role,
                )
                verification = evidence_loop.verify_evidence_bundle(destination)
                self.assertFalse(verification["valid"])
                self.assertTrue(
                    any(
                        target_role in issue and "does not match" in issue
                        for issue in verification["issues"]
                    ),
                    verification["issues"],
                )
                self.assertFalse(verification["promotion_allowed"])

    def test_bundle_verification_rejects_role_absent_from_audit_index(self) -> None:
        source = self.root / "bundle-index-source"
        evidence_loop.materialize_evidence_bundle(
            self.candidate,
            self.visual_report,
            self.runtime_report,
            self.plan_path,
            source,
        )
        destination = self.root / "bundle-renamed-role"
        shutil.copytree(source, destination)
        manifest_path = destination / "manifest.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        engine = next(
            item for item in manifest["artifacts"] if item["role"] == "engine:visual"
        )
        engine["role"] = "engine:renamed"
        self._write_bundle_manifest(destination, manifest)
        verification = evidence_loop.verify_evidence_bundle(destination)
        self.assertFalse(verification["valid"])
        self.assertTrue(
            any("materialized_roles" in issue for issue in verification["issues"]),
            verification["issues"],
        )
        self.assertFalse(verification["promotion_allowed"])

    def test_bundle_verification_reopens_candidate_for_bsp_claims(self) -> None:
        source = self.root / "bundle-candidate-source"
        evidence_loop.materialize_evidence_bundle(
            self.candidate,
            self.visual_report,
            self.runtime_report,
            self.plan_path,
            source,
        )
        variants = ("expected-member", "member-count", "inner-hash")
        for index, variant in enumerate(variants):
            with self.subTest(variant=variant):
                destination = self.root / f"bundle-candidate-claim-{index}"
                shutil.copytree(source, destination)
                manifest_path = destination / "manifest.json"
                manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
                audit_entry = next(
                    item
                    for item in manifest["artifacts"]
                    if item["role"] == "audit"
                )
                audit = json.loads(
                    (destination / audit_entry["object"]).read_text(encoding="utf-8")
                )
                if variant == "expected-member":
                    fabricated = "maps/dm/fabricated.bsp"
                    manifest["expected_bsp_member"] = fabricated
                    audit["candidate"]["expected_bsp_member"] = fabricated
                elif variant == "member-count":
                    audit["candidate"]["member_count"] = 999
                else:
                    fabricated_hash = "0" * 64
                    audit["candidate"]["bsp_sha256"] = fabricated_hash
                    bsp_member = next(
                        item
                        for item in audit["candidate"]["members"]
                        if item["path"].endswith(".bsp")
                    )
                    bsp_member["sha256"] = fabricated_hash
                self._write_bundle_audit(
                    destination,
                    manifest,
                    audit,
                )
                verification = evidence_loop.verify_evidence_bundle(destination)
                self.assertFalse(verification["valid"])
                self.assertTrue(
                    any("candidate" in issue for issue in verification["issues"]),
                    verification["issues"],
                )
                self.assertFalse(verification["promotion_allowed"])

    def test_bundle_verification_rejects_scorer_not_executing_verifier(self) -> None:
        source = self.root / "bundle-scorer-source"
        evidence_loop.materialize_evidence_bundle(
            self.candidate,
            self.visual_report,
            self.runtime_report,
            self.plan_path,
            source,
        )
        destination = self.root / "bundle-scorer-substituted"
        shutil.copytree(source, destination)
        manifest_path = destination / "manifest.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        by_role = {item["role"]: item for item in manifest["artifacts"]}
        scorer = by_role["scorer"]
        audit_entry = by_role["audit"]
        old_scorer_object = scorer["object"]
        replacement = b"not the executing evidence verifier\n"
        replacement_sha = hashlib.sha256(replacement).hexdigest()
        replacement_object = f"objects/sha256/{replacement_sha}"
        (destination / replacement_object).write_bytes(replacement)
        scorer.update(
            {
                "bytes": len(replacement),
                "sha256": replacement_sha,
                "object": replacement_object,
            }
        )
        manifest["audit_scorer_sha256"] = replacement_sha
        audit = json.loads(
            (destination / audit_entry["object"]).read_text(encoding="utf-8")
        )
        scorer_record = next(
            item for item in audit["materialized_roles"] if item["role"] == "scorer"
        )
        scorer_record.update(
            {
                "bytes": len(replacement),
                "sha256": replacement_sha,
            }
        )
        if old_scorer_object != replacement_object:
            (destination / old_scorer_object).unlink()
        self._write_bundle_audit(destination, manifest, audit)
        verification = evidence_loop.verify_evidence_bundle(destination)
        self.assertFalse(verification["valid"])
        self.assertIn(
            "bundled scorer does not match the currently executing evidence verifier",
            verification["issues"],
        )
        self.assertEqual(verification["executing_scorer_sha256"], sha256(SCRIPT))
        self.assertFalse(verification["promotion_allowed"])

    def test_bundle_verification_rejects_manifest_audit_field_divergence(self) -> None:
        source = self.root / "bundle-manifest-source"
        evidence_loop.materialize_evidence_bundle(
            self.candidate,
            self.visual_report,
            self.runtime_report,
            self.plan_path,
            source,
        )
        variants = (
            ("map-name", "map_name", "fabricated_map"),
            ("technical-ready", "technical_ready_for_human_review", False),
        )
        for index, (name, field, value) in enumerate(variants):
            with self.subTest(field=field):
                destination = self.root / f"bundle-manifest-divergence-{index}"
                shutil.copytree(source, destination)
                manifest_path = destination / "manifest.json"
                manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
                if field == "technical_ready_for_human_review":
                    value = not manifest[field]
                manifest[field] = value
                self._write_bundle_manifest(destination, manifest)
                verification = evidence_loop.verify_evidence_bundle(destination)
                self.assertFalse(verification["valid"])
                self.assertIn(
                    f"manifest {field} does not match bundled audit",
                    verification["issues"],
                )
                self.assertFalse(verification["promotion_allowed"])

    def test_bundle_verification_rejects_coordinated_visual_report_rewrites(self) -> None:
        source = self.root / "bundle-visual-report-source"
        evidence_loop.materialize_evidence_bundle(
            self.candidate,
            self.visual_report,
            self.runtime_report,
            self.plan_path,
            source,
        )
        variants = (
            (
                "raw-log",
                "raw_log:visual path does not match bundled audit raw log",
            ),
            (
                "runtime-log",
                "raw_log:visual runtimeLog path does not match bundled audit raw log",
            ),
            (
                "map-name",
                "bundled visual report mapName does not match manifest",
            ),
            (
                "candidate-hash",
                "candidate hash does not match bundled visual report candidate",
            ),
            (
                "engine-hash",
                "engine:visual hash does not match bundled visual report engine",
            ),
            (
                "engine-path",
                "engine:visual path does not match bundled visual launch provenance",
            ),
            (
                "arguments",
                "bundled visual report arguments do not match audited visual launch provenance",
            ),
            (
                "fs-basepath",
                "bundled visual report fsBasepath does not match audited visual launch provenance",
            ),
            (
                "fs-homepath",
                "bundled visual report fsHomepath does not match audited visual launch provenance",
            ),
            (
                "first-screenshot",
                "screenshot:000:forward hash does not match bundled visual report screenshot 0",
            ),
            (
                "runtime-package",
                "runtime_package:visual hash does not match bundled visual report runtime package",
            ),
        )
        for index, (variant, expected_issue) in enumerate(variants):
            with self.subTest(variant=variant):
                destination = self.root / f"bundle-visual-report-rewrite-{index}"
                self._rewrite_bundle_visual_report(
                    source,
                    destination,
                    variant,
                )
                verification = evidence_loop.verify_evidence_bundle(destination)
                self.assertFalse(verification["valid"])
                self.assertIn(expected_issue, verification["issues"])
                self.assertFalse(verification["promotion_allowed"])

    def test_bundle_verification_rejects_coordinated_runtime_report_rewrites(self) -> None:
        source = self.root / "bundle-runtime-report-source"
        evidence_loop.materialize_evidence_bundle(
            self.candidate,
            self.visual_report,
            self.runtime_report,
            self.plan_path,
            source,
        )
        variants = (
            ("map-name", "bundled runtime report mapName does not match manifest"),
            (
                "candidate-hash",
                "candidate hash does not match bundled runtime report candidate",
            ),
            (
                "raw-log",
                "raw_log:bot path does not match bundled audit raw log",
            ),
            (
                "runtime-package",
                "runtime_package:bot hash does not match bundled runtime report runtime package",
            ),
        )
        for index, (variant, expected_issue) in enumerate(variants):
            with self.subTest(variant=variant):
                destination = self.root / f"bundle-runtime-report-rewrite-{index}"
                self._rewrite_bundle_runtime_report(source, destination, variant)
                verification = evidence_loop.verify_evidence_bundle(destination)
                self.assertFalse(verification["valid"])
                self.assertIn(expected_issue, verification["issues"])
                self.assertFalse(verification["promotion_allowed"])

    def test_bundle_verification_binds_runtime_report_engine_hash(self) -> None:
        source = self.root / "bundle-runtime-engine-source"
        evidence_loop.materialize_evidence_bundle(
            self.candidate,
            self.visual_report,
            self.runtime_report,
            self.plan_path,
            source,
        )
        destination = self.root / "bundle-runtime-engine-rewrite"
        self._rewrite_bundle_runtime_report(source, destination, "engine-hash")
        verification = evidence_loop.verify_evidence_bundle(destination)
        self.assertFalse(verification["valid"])
        for expected_issue in (
            "engine:bot hash does not match bundled runtime report engine",
            "bundled runtime report engine hash does not match audited bot launch provenance",
            "bundled runtime report engine hash does not match audited runtime summary",
        ):
            with self.subTest(issue=expected_issue):
                self.assertIn(expected_issue, verification["issues"])
        self.assertFalse(verification["promotion_allowed"])

    def test_bundle_verification_binds_runtime_report_bot_activity(self) -> None:
        source = self.root / "bundle-runtime-activity-source"
        evidence_loop.materialize_evidence_bundle(
            self.candidate,
            self.visual_report,
            self.runtime_report,
            self.plan_path,
            source,
        )
        destination = self.root / "bundle-runtime-activity-rewrite"
        self._rewrite_bundle_runtime_report(source, destination, "bot-activity")
        verification = evidence_loop.verify_evidence_bundle(destination)
        self.assertFalse(verification["valid"])
        for report_field in (
            "botsEntered",
            "combatEvents",
            "minimumCombatEvents",
        ):
            with self.subTest(field=report_field):
                self.assertIn(
                    f"bundled runtime report {report_field} does not match audited bot activity",
                    verification["issues"],
                )
        self.assertFalse(verification["promotion_allowed"])

    def test_bundle_verification_recounts_raw_bot_activity(self) -> None:
        source = self.root / "bundle-runtime-recount-source"
        evidence_loop.materialize_evidence_bundle(
            self.candidate,
            self.visual_report,
            self.runtime_report,
            self.plan_path,
            source,
        )
        destination = self.root / "bundle-runtime-recount-rewrite"
        self._rewrite_bundle_runtime_report(
            source,
            destination,
            "bot-activity-coordinated",
        )
        verification = evidence_loop.verify_evidence_bundle(destination)
        self.assertFalse(verification["valid"])
        for expected_issue in (
            "bundled runtime report botsEntered does not match raw_log:bot recount",
            "bundled audit bot_activity bots_entered does not match raw_log:bot recount",
            "bundled runtime report combatEvents does not match raw_log:bot recount",
            "bundled audit bot_activity combat_events does not match raw_log:bot recount",
        ):
            with self.subTest(issue=expected_issue):
                self.assertIn(expected_issue, verification["issues"])
        self.assertFalse(verification["promotion_allowed"])

    def test_bundle_verification_enforces_combat_threshold(self) -> None:
        source = self.root / "bundle-runtime-threshold-source"
        evidence_loop.materialize_evidence_bundle(
            self.candidate,
            self.visual_report,
            self.runtime_report,
            self.plan_path,
            source,
        )
        destination = self.root / "bundle-runtime-threshold-rewrite"
        self._rewrite_bundle_runtime_report(
            source,
            destination,
            "combat-threshold",
        )
        verification = evidence_loop.verify_evidence_bundle(destination)
        self.assertFalse(verification["valid"])
        self.assertIn(
            "raw_log:bot combat event recount does not meet bundled runtime report minimumCombatEvents",
            verification["issues"],
        )
        self.assertFalse(verification["promotion_allowed"])

    def test_bundle_verification_requires_positive_combat_threshold(self) -> None:
        source = self.root / "bundle-runtime-threshold-type-source"
        evidence_loop.materialize_evidence_bundle(
            self.candidate,
            self.visual_report,
            self.runtime_report,
            self.plan_path,
            source,
        )
        for index, variant in enumerate(
            (
                "combat-threshold-zero",
                "combat-threshold-bool",
                "combat-threshold-string",
            )
        ):
            with self.subTest(variant=variant):
                destination = self.root / f"bundle-runtime-threshold-type-{index}"
                self._rewrite_bundle_runtime_report(
                    source,
                    destination,
                    variant,
                )
                verification = evidence_loop.verify_evidence_bundle(destination)
                self.assertFalse(verification["valid"])
                self.assertIn(
                    "bundled runtime report minimumCombatEvents must be a positive integer",
                    verification["issues"],
                )
                self.assertFalse(verification["promotion_allowed"])

    def test_bundle_verification_recounts_runtime_load_observations(self) -> None:
        source = self.root / "bundle-runtime-load-source"
        evidence_loop.materialize_evidence_bundle(
            self.candidate,
            self.visual_report,
            self.runtime_report,
            self.plan_path,
            source,
        )
        destination = self.root / "bundle-runtime-load-rewrite"
        self._rewrite_bundle_runtime_report(
            source,
            destination,
            "runtime-load-observations",
        )
        verification = evidence_loop.verify_evidence_bundle(destination)
        self.assertFalse(verification["valid"])
        for expected_issue in (
            "bundled runtime report bspParse count does not match raw_log:bot recount",
            "bundled audit runtime bsp_parse_observations does not match raw_log:bot recount",
            "bundled runtime report recast count does not match raw_log:bot recount",
            "bundled audit runtime recast_observations does not match raw_log:bot recount",
        ):
            with self.subTest(issue=expected_issue):
                self.assertIn(expected_issue, verification["issues"])
        self.assertFalse(verification["promotion_allowed"])

    def test_bundle_verification_binds_runtime_load_observation_text(self) -> None:
        source = self.root / "bundle-runtime-load-text-source"
        evidence_loop.materialize_evidence_bundle(
            self.candidate,
            self.visual_report,
            self.runtime_report,
            self.plan_path,
            source,
        )
        destination = self.root / "bundle-runtime-load-text-rewrite"
        self._rewrite_bundle_runtime_report(
            source,
            destination,
            "runtime-load-fabricated",
        )
        verification = evidence_loop.verify_evidence_bundle(destination)
        self.assertFalse(verification["valid"])
        for expected_issue in (
            "bundled runtime report bspParse[0] does not exist exactly in raw_log:bot",
            "bundled runtime report recast[0] does not exist exactly in raw_log:bot",
        ):
            with self.subTest(issue=expected_issue):
                self.assertIn(expected_issue, verification["issues"])
        self.assertFalse(verification["promotion_allowed"])

    def test_bundle_verification_replays_runtime_gate(self) -> None:
        source = self.root / "bundle-runtime-gate-source"
        evidence_loop.materialize_evidence_bundle(
            self.candidate,
            self.visual_report,
            self.runtime_report,
            self.plan_path,
            source,
        )
        destination = self.root / "bundle-runtime-gate-rewrite"
        self._rewrite_bundle_runtime_report(
            source,
            destination,
            "runtime-script-error",
        )
        verification = evidence_loop.verify_evidence_bundle(destination)
        self.assertFalse(verification["valid"])
        self.assertIn(
            "bundled audit runtime_load gate does not match replayed runtime report",
            verification["issues"],
        )
        self.assertFalse(verification["promotion_allowed"])

    def test_bundle_verification_replays_fixed_view_capture(self) -> None:
        source = self.root / "bundle-plan-capture-source"
        evidence_loop.materialize_evidence_bundle(
            self.candidate,
            self.visual_report,
            self.runtime_report,
            self.plan_path,
            source,
        )
        destination = self.root / "bundle-plan-capture-rewrite"
        self._rewrite_bundle_evidence_plan(
            source,
            destination,
            required_view_category="fabricated_category",
        )
        verification = evidence_loop.verify_evidence_bundle(destination)
        self.assertFalse(verification["valid"])
        for expected_issue in (
            (
                "bundled audit fixed_view_capture gate does not match replayed "
                "visual report and evidence plan"
            ),
            (
                "bundled audit capture summary does not match replayed visual "
                "report and evidence plan"
            ),
            (
                "bundled audit capture_integrity_and_coverage score does not "
                "match replayed visual report and evidence plan"
            ),
        ):
            with self.subTest(issue=expected_issue):
                self.assertIn(expected_issue, verification["issues"])
        self.assertFalse(verification["promotion_allowed"])

    def test_bundle_verification_replays_semantic_visual_review(self) -> None:
        source = self.root / "bundle-plan-visual-review-source"
        self.plan["visual_review"]["views"][0]["blocking_defects"] = [
            "fixture blocking defect"
        ]
        self._write_json(self.plan_path, self.plan)
        evidence_loop.materialize_evidence_bundle(
            self.candidate,
            self.visual_report,
            self.runtime_report,
            self.plan_path,
            source,
        )
        destination = self.root / "bundle-plan-visual-review-rewrite"
        self._rewrite_bundle_evidence_plan(
            source,
            destination,
            clear_blocking_defects=True,
        )
        verification = evidence_loop.verify_evidence_bundle(destination)
        self.assertFalse(verification["valid"])
        self.assertIn(
            (
                "bundled audit semantic_visual_review gate does not match "
                "replayed evidence plan"
            ),
            verification["issues"],
        )
        self.assertIn(
            (
                "bundled audit blocking_visual_defects do not match replayed "
                "evidence plan"
            ),
            verification["issues"],
        )
        self.assertFalse(verification["promotion_allowed"])

    def test_bundle_verification_binds_evidence_plan_bsp_member(self) -> None:
        source = self.root / "bundle-plan-bsp-member-source"
        evidence_loop.materialize_evidence_bundle(
            self.candidate,
            self.visual_report,
            self.runtime_report,
            self.plan_path,
            source,
        )
        destination = self.root / "bundle-plan-bsp-member-rewrite"
        self._rewrite_bundle_evidence_plan(
            source,
            destination,
            expected_bsp_member="maps/dm/fabricated.bsp",
        )
        verification = evidence_loop.verify_evidence_bundle(destination)
        self.assertFalse(verification["valid"])
        self.assertIn(
            "bundled evidence plan expected_bsp_member does not match manifest",
            verification["issues"],
        )
        self.assertIn(
            (
                "bundled evidence plan expected_bsp_member does not match "
                "bundled audit candidate"
            ),
            verification["issues"],
        )
        self.assertFalse(verification["promotion_allowed"])

    def test_bundle_verification_binds_evidence_plan_map_name(self) -> None:
        source = self.root / "bundle-plan-map-name-source"
        evidence_loop.materialize_evidence_bundle(
            self.candidate,
            self.visual_report,
            self.runtime_report,
            self.plan_path,
            source,
        )
        destination = self.root / "bundle-plan-map-name-rewrite"
        self._rewrite_bundle_evidence_plan(
            source,
            destination,
            map_name="fabricated_map",
        )
        verification = evidence_loop.verify_evidence_bundle(destination)
        self.assertFalse(verification["valid"])
        self.assertIn(
            "bundled evidence plan map_name does not match manifest",
            verification["issues"],
        )
        self.assertIn(
            "bundled evidence plan map_name does not match bundled audit",
            verification["issues"],
        )
        self.assertFalse(verification["promotion_allowed"])

    def test_bundle_verification_replays_bot_activity_from_evidence_plan(
        self,
    ) -> None:
        source = self.root / "bundle-bot-plan-source"
        evidence_loop.materialize_evidence_bundle(
            self.candidate,
            self.visual_report,
            self.runtime_report,
            self.plan_path,
            source,
        )
        destination = self.root / "bundle-bot-plan-rewrite"
        self._rewrite_bundle_evidence_plan(
            source,
            destination,
            expected_bot_count=999,
        )
        verification = evidence_loop.verify_evidence_bundle(destination)
        self.assertFalse(verification["valid"])
        self.assertIn(
            "bundled audit bot_entry_and_combat gate does not match replayed runtime report and evidence plan",
            verification["issues"],
        )
        self.assertIn(
            "bundled audit bot_activity summary does not match replayed runtime report and evidence plan",
            verification["issues"],
        )
        self.assertFalse(verification["promotion_allowed"])

    def test_report_artifacts_do_not_depend_on_process_cwd(self) -> None:
        repository = self.root / "repo"
        evidence = repository / "generated" / self.map_name / "evidence"
        reports = evidence / "reports"
        logs = evidence / "logs"
        screenshots = evidence / "screenshots"
        for directory in (reports, logs, screenshots):
            directory.mkdir(parents=True, exist_ok=True)

        visual_log = logs / "visual.log"
        bot_log = logs / "bot.log"
        shutil.copyfile(self.visual_log, visual_log)
        shutil.copyfile(self.runtime_log, bot_log)
        copied_screenshots = []
        for index, screenshot in enumerate(self.screenshots):
            copied = screenshots / f"shot{index:04}.tga"
            shutil.copyfile(screenshot, copied)
            copied_screenshots.append(copied)

        visual = json.loads(self.visual_report.read_text(encoding="utf-8"))
        runtime = json.loads(self.runtime_report.read_text(encoding="utf-8"))
        visual["log"] = f"generated/{self.map_name}/evidence/logs/visual.log"
        runtime["log"] = f"generated/{self.map_name}/evidence/logs/bot.log"
        for index, item in enumerate(visual["screenshots"]):
            item["path"] = (
                f"generated/{self.map_name}/evidence/screenshots/"
                f"{copied_screenshots[index].name}"
            )
        nested_visual = reports / "visual.json"
        nested_runtime = reports / "runtime.json"
        nested_plan = reports / "plan.json"
        self._write_json(nested_visual, visual)
        self._write_json(nested_runtime, runtime)
        self._write_json(nested_plan, self.plan)

        outside = self.root / "outside"
        outside.mkdir()
        original_cwd = Path.cwd()
        try:
            os.chdir(outside)
            manifest = evidence_loop.materialize_evidence_bundle(
                self.candidate,
                nested_visual,
                nested_runtime,
                nested_plan,
                outside / "bundle",
            )
        finally:
            os.chdir(original_cwd)
        self.assertEqual(manifest["candidate_sha256"], sha256(self.candidate))
        self.assertTrue(
            evidence_loop.verify_evidence_bundle(outside / "bundle")["valid"]
        )

    def test_materialize_bundle_refuses_existing_destination(self) -> None:
        destination = self.root / "existing-bundle"
        destination.mkdir()
        with self.assertRaises(evidence_loop.EvidenceError):
            evidence_loop.materialize_evidence_bundle(
                self.candidate,
                self.visual_report,
                self.runtime_report,
                self.plan_path,
                destination,
            )

    def test_bundle_verification_detects_tampering(self) -> None:
        destination = self.root / "tampered-bundle"
        manifest = evidence_loop.materialize_evidence_bundle(
            self.candidate,
            self.visual_report,
            self.runtime_report,
            self.plan_path,
            destination,
        )
        candidate = next(
            item for item in manifest["artifacts"] if item["role"] == "candidate"
        )
        (destination / candidate["object"]).write_bytes(b"mixed-candidate")
        (destination / "unexpected.txt").write_text("mixed", encoding="utf-8")
        verification = evidence_loop.verify_evidence_bundle(destination)
        self.assertFalse(verification["valid"])
        self.assertTrue(
            any("hash mismatch" in issue for issue in verification["issues"])
        )
        self.assertTrue(
            any(
                "unexpected bundle files" in issue for issue in verification["issues"]
            )
        )

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
