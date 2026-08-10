#!/usr/bin/env python3

from __future__ import annotations

import importlib.util
import json
import sys
import unittest
from copy import deepcopy
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

spec = importlib.util.spec_from_file_location("build_manifest_module", ROOT / "scripts" / "build-manifest.py")
build_module = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(build_module)

from mirrorlib import load_schema_and_validate, validate_manifest  # noqa: E402


class ManifestTests(unittest.TestCase):
    def setUp(self) -> None:
        self.entry = json.loads((ROOT / "tests" / "fixtures" / "release-150.json").read_text())

    def test_builds_valid_manifest(self) -> None:
        manifest = build_module.build_manifest(self.entry, None, 10)
        self.assertEqual(manifest["latest"], self.entry["version"])
        load_schema_and_validate(manifest, ROOT / "schemas" / "manifest.schema.json")

    def test_sorts_numerically_and_truncates(self) -> None:
        older = deepcopy(self.entry)
        older["version"] = "99.0.1.1"
        for artifact in older["artifacts"]:
            artifact["filename"] = artifact["filename"].replace("150.0.7000.1", "99.0.1.1")
            artifact["url"] = artifact["url"].replace("150.0.7000.1", "99.0.1.1")
            artifact["checksum_url"] = artifact["checksum_url"].replace("150.0.7000.1", "99.0.1.1")
            artifact["source_url"] = artifact["source_url"].replace("150.0.7000.1", "99.0.1.1")
        existing = build_module.build_manifest(older, None, 10)
        result = build_module.build_manifest(self.entry, existing, 1)
        self.assertEqual([self.entry["version"]], [item["version"] for item in result["versions"]])

    def entry_for(self, version: str) -> dict:
        entry = deepcopy(self.entry)
        original = entry["version"]
        entry["version"] = version
        for artifact in entry["artifacts"]:
            for key in ("filename", "url", "checksum_url", "source_url"):
                artifact[key] = artifact[key].replace(original, version)
        return entry

    def test_preserves_pinned_history_while_rolling_new_versions(self) -> None:
        pinned = "115.0.5790.170"
        manifest = build_module.build_manifest(self.entry_for(pinned), None, 3, [pinned])
        for version in ("150.0.7871.124", "151.0.7922.77", "152.0.8000.1"):
            manifest = build_module.build_manifest(self.entry_for(version), manifest, 3, [pinned])
        self.assertEqual(
            ["152.0.8000.1", "151.0.7922.77", pinned],
            [item["version"] for item in manifest["versions"]],
        )

    def test_historical_config_contains_five_unique_major_versions(self) -> None:
        versions = build_module.load_pinned_versions(
            ROOT / "config" / "historical-stable-versions.json"
        )
        self.assertEqual(5, len(versions))
        self.assertEqual([115, 120, 130, 140, 150], [int(v.split(".")[0]) for v in versions])

    def test_manifest_capacity_must_leave_room_for_current_stable(self) -> None:
        with self.assertRaisesRegex(ValueError, "at least one slot"):
            build_module.build_manifest(self.entry, None, 1, ["115.0.5790.170"])

    def test_idempotent_entry_preserves_mirrored_at(self) -> None:
        existing = build_module.build_manifest(self.entry, None, 10)
        repeated = deepcopy(self.entry)
        repeated["mirrored_at"] = "2026-08-08T00:00:00Z"
        result = build_module.build_manifest(repeated, existing, 10)
        self.assertEqual("2026-08-01T00:00:00Z", result["versions"][0]["mirrored_at"])
        self.assertEqual(existing, result)

    def test_rejects_changed_existing_version(self) -> None:
        existing = build_module.build_manifest(self.entry, None, 10)
        changed = deepcopy(self.entry)
        changed["artifacts"][0]["sha256"] = "e" * 64
        with self.assertRaisesRegex(ValueError, "refusing to change"):
            build_module.build_manifest(changed, existing, 10)

    def test_rejects_duplicate_platform_tuple(self) -> None:
        manifest = build_module.build_manifest(self.entry, None, 10)
        manifest["versions"][0]["artifacts"][1]["os"] = "linux"
        manifest["versions"][0]["artifacts"][1]["arch"] = "x64"
        with self.assertRaisesRegex(ValueError, "duplicate artifact"):
            validate_manifest(manifest)

    def test_rejects_non_contract_object_path(self) -> None:
        manifest = build_module.build_manifest(self.entry, None, 10)
        manifest["versions"][0]["artifacts"][0]["url"] = (
            "https://aliyun-oss.yaklang.com/wrong/chrome-cft-150.0.7000.1-linux-x64.zip"
        )
        manifest["versions"][0]["artifacts"][0]["checksum_url"] = (
            f"{manifest['versions'][0]['artifacts'][0]['url']}.sha256.txt"
        )
        with self.assertRaisesRegex(ValueError, "URL path"):
            validate_manifest(manifest)


if __name__ == "__main__":
    unittest.main()
