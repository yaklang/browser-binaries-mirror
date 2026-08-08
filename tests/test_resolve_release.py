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

    def test_version_input_is_only_a_stable_guard(self) -> None:
        selected = resolve_module.select_release(self.metadata, "151.0.7922.77")
        self.assertEqual("151.0.7922.77", selected["version"])

    def test_rejects_non_stable_requested_version(self) -> None:
        with self.assertRaisesRegex(ValueError, "not the current official Stable"):
            resolve_module.select_release(self.metadata, "152.0.8000.1")


if __name__ == "__main__":
    unittest.main()
