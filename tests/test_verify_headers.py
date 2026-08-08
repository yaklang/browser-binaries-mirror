#!/usr/bin/env python3

from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

spec = importlib.util.spec_from_file_location("verify_public_module", ROOT / "scripts" / "verify-public.py")
verify_module = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(verify_module)


class PublicHeaderTests(unittest.TestCase):
    def test_accepts_custom_cdn_text_cache_policy(self) -> None:
        verify_module.require_headers(
            {
                "content-length": "105",
                "content-type": "text/plain; charset=utf-8",
                "cache-control": "max-age=60",
            },
            kind="checksum",
        )

    def test_rejects_missing_checksum_cache_policy(self) -> None:
        with self.assertRaisesRegex(ValueError, "Cache-Control"):
            verify_module.require_headers(
                {"content-length": "105", "content-type": "text/plain; charset=utf-8"},
                kind="checksum",
            )

    def test_accepts_custom_cdn_manifest_cache_policy(self) -> None:
        verify_module.require_headers(
            {
                "content-length": "3338",
                "content-type": "application/json; charset=utf-8",
                "cache-control": "max-age=60",
            },
            kind="manifest",
        )


if __name__ == "__main__":
    unittest.main()
