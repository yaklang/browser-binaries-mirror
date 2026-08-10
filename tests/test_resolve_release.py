#!/usr/bin/env python3

from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
spec = importlib.util.spec_from_file_location("resolve_release_module", ROOT / "scripts" / "resolve-release.py")
resolve_module = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(resolve_module)


class StableSelectionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.metadata = {
            "channels": {
                "Stable": {"version": "151.0.7922.77", "revision": "1654411", "downloads": {}}
            }
        }

    def test_always_selects_stable(self) -> None:
        self.assertEqual(
            "151.0.7922.77",
            resolve_module.select_release(self.metadata, None)["version"],
        )

    def test_current_version_input_reuses_current_stable(self) -> None:
        selected = resolve_module.select_release(self.metadata, "151.0.7922.77")
        self.assertEqual("151.0.7922.77", selected["version"])

    def historical_metadata(self, version: str, *, omit_platform: str | None = None) -> tuple[dict, dict]:
        known_good = {"versions": [{"version": version, "revision": "123", "downloads": {}}]}
        history = {
            "versions": [
                {
                    "name": f"chrome/platforms/{platform}/channels/stable/versions/{version}",
                    "version": version,
                }
                for platform in ("linux", "mac", "mac_arm64", "win64")
                if platform != omit_platform
            ]
        }
        return known_good, history

    def test_accepts_historical_version_that_was_stable_on_every_platform(self) -> None:
        version = "140.0.7339.207"
        known_good, history = self.historical_metadata(version)
        selected = resolve_module.select_release(self.metadata, version, known_good, history)
        self.assertEqual(version, selected["version"])

    def test_rejects_historical_version_missing_one_stable_platform(self) -> None:
        version = "140.0.7339.207"
        known_good, history = self.historical_metadata(version, omit_platform="linux")
        with self.assertRaisesRegex(ValueError, "not Stable on every mirrored platform"):
            resolve_module.select_release(self.metadata, version, known_good, history)

    def test_rejects_non_known_good_historical_version(self) -> None:
        version = "140.0.7339.999"
        _, history = self.historical_metadata(version)
        with self.assertRaisesRegex(ValueError, "not a known-good CfT version"):
            resolve_module.select_release(self.metadata, version, {"versions": []}, history)


if __name__ == "__main__":
    unittest.main()
