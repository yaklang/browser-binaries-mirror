#!/usr/bin/env python3

from __future__ import annotations

import gzip
import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

spec = importlib.util.spec_from_file_location("verify_public_module", ROOT / "scripts" / "verify-public.py")
verify_module = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(verify_module)

from mirrorlib import load_json  # noqa: E402


class PublicHeaderTests(unittest.TestCase):
    def test_decompresses_gzip_http_body(self) -> None:
        class Response:
            headers = {"Content-Encoding": "gzip"}

            def read(self) -> bytes:
                return gzip.compress(b'{"latest":"151.0.7922.77"}')

            def __enter__(self):
                return self

            def __exit__(self, *args):
                return None

        original = verify_module.request
        self.addCleanup(setattr, verify_module, "request", original)
        verify_module.request = lambda *args, **kwargs: Response()
        self.assertEqual(b'{"latest":"151.0.7922.77"}', verify_module.get_bytes("https://example.test"))

    def test_decompresses_gzip_magic_without_content_encoding(self) -> None:
        class Response:
            headers = {}

            def read(self) -> bytes:
                return gzip.compress(b'{"latest":"151.0.7922.77"}')

            def __enter__(self):
                return self

            def __exit__(self, *args):
                return None

        original = verify_module.request
        self.addCleanup(setattr, verify_module, "request", original)
        verify_module.request = lambda *args, **kwargs: Response()
        self.assertEqual(b'{"latest":"151.0.7922.77"}', verify_module.get_bytes("https://example.test"))

    def test_load_json_accepts_gzip_cache_variant(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "manifest.json"
            expected = {"latest": "151.0.7922.77"}
            path.write_bytes(gzip.compress(json.dumps(expected).encode("utf-8")))
            self.assertEqual(expected, load_json(path))

    def test_cache_bust_can_pair_requests_with_one_token(self) -> None:
        manifest_url = verify_module.cache_bust("https://example.test/manifest.json", token=42)
        checksum_url = verify_module.cache_bust("https://example.test/manifest.json.sha256.txt", token=42)
        self.assertTrue(manifest_url.endswith("mirror_verify=42"))
        self.assertTrue(checksum_url.endswith("mirror_verify=42"))

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
